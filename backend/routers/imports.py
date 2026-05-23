import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import User, ImportJob, Holding, Transaction
from dependencies import get_current_user
from importers import detect_format, get_importer

router = APIRouter(prefix="/api/imports", tags=["imports"])


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    source_platform: str = Form("generic"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    content = await file.read()

    # Detect format
    fmt = source_platform
    if source_platform in ("generic", "other"):
        preview = content[:500].decode("utf-8", errors="replace")
        if file.filename and file.filename.lower().endswith(".csv"):
            try:
                headers = next(csv.reader(io.StringIO(preview)))
                fmt = detect_format(headers, preview)
            except StopIteration:
                fmt = "generic"
        else:
            fmt = "cams_cas" if "Consolidated Account Statement" in preview else "generic"

    job = ImportJob(
        user_id=user.id,
        source_platform=fmt,
        file_name=file.filename,
        status="processing",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Parse in background (simplified: parse inline for now)
    importer = get_importer(fmt)
    try:
        holdings_dtos = await importer.parse(content, file.filename or "upload.csv")
        preview_data = [
            {
                "instrument_type": h.instrument_type,
                "display_name": h.display_name,
                "asset_class": h.asset_class,
                "invested_amount": h.invested_amount,
                "current_value": h.current_value,
                "metadata": h.metadata,
                "confidence_score": h.confidence_score,
                "warnings": h.warnings,
                "transaction_count": len(h.transactions),
            }
            for h in holdings_dtos
        ]
        job.status = "preview_ready"
        job.preview_data = {"holdings": preview_data, "dtos_serialized": [
            {**d, "transactions": [
                {"transaction_date": str(t.transaction_date), "transaction_type": t.transaction_type,
                 "amount": t.amount, "units": t.units, "price": t.price, "notes": t.notes}
                for t in h.transactions
            ]}
            for d, h in zip(preview_data, holdings_dtos)
        ]}
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)

    await db.commit()
    return {"import_job_id": str(job.id), "status": job.status}


@router.get("/{job_id}/preview")
async def get_preview(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(ImportJob).where(ImportJob.id == job_id, ImportJob.user_id == user.id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")

    preview = job.preview_data or {}
    return {
        "status": job.status,
        "holdings_parsed": preview.get("holdings", []),
        "warnings": job.warnings,
        "error_message": job.error_message,
    }


@router.post("/{job_id}/confirm")
async def confirm_import(
    job_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(ImportJob).where(ImportJob.id == job_id, ImportJob.user_id == user.id))
    job = result.scalar_one_or_none()
    if not job or job.status != "preview_ready":
        raise HTTPException(status_code=400, detail="Job not in preview_ready state")

    confirmed_indices = body.get("confirmed_indices", [])
    skipped_indices = set(body.get("skipped_indices", []))
    dtos = job.preview_data.get("dtos_serialized", [])

    created = updated = tx_created = 0

    for i, dto in enumerate(dtos):
        if i in skipped_indices:
            continue
        if confirmed_indices and i not in confirmed_indices:
            continue

        # Deduplication: check by instrument_type + key metadata field
        existing = await _find_existing_holding(db, user.id, dto)
        if existing:
            existing.invested_amount = dto["invested_amount"]
            existing.current_value = dto["current_value"]
            existing.metadata_ = dto["metadata"]
            updated += 1
            holding = existing
        else:
            holding = Holding(
                user_id=user.id,
                instrument_type=dto["instrument_type"],
                display_name=dto["display_name"],
                asset_class=dto["asset_class"],
                invested_amount=dto["invested_amount"],
                current_value=dto["current_value"],
                metadata_=dto["metadata"],
            )
            db.add(holding)
            await db.flush()
            created += 1

        for tx in dto.get("transactions", []):
            from datetime import date
            t = Transaction(
                user_id=user.id,
                holding_id=holding.id,
                transaction_date=date.fromisoformat(tx["transaction_date"]),
                transaction_type=tx["transaction_type"],
                amount=tx["amount"],
                units=tx.get("units"),
                price=tx.get("price"),
                notes=tx.get("notes"),
                import_source=job.source_platform,
            )
            db.add(t)
            tx_created += 1

    if user.onboarding_step < 1:
        user.onboarding_step = 1
    job.status = "completed"
    job.holdings_created = created
    job.holdings_updated = updated
    job.transactions_created = tx_created
    job.completed_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "holdings_created": created,
        "holdings_updated": updated,
        "transactions_created": tx_created,
    }


@router.get("/history")
async def import_history(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ImportJob).where(ImportJob.user_id == user.id).order_by(ImportJob.created_at.desc()).limit(50)
    )
    jobs = result.scalars().all()
    return [
        {
            "id": str(j.id),
            "source_platform": j.source_platform,
            "file_name": j.file_name,
            "status": j.status,
            "holdings_created": j.holdings_created,
            "holdings_updated": j.holdings_updated,
            "transactions_created": j.transactions_created,
            "created_at": j.created_at,
            "completed_at": j.completed_at,
        }
        for j in jobs
    ]


async def _find_existing_holding(db, user_id, dto: dict):
    from sqlalchemy import and_
    q = select(Holding).where(
        Holding.user_id == user_id,
        Holding.is_active == True,
        Holding.instrument_type == dto["instrument_type"],
        Holding.display_name == dto["display_name"],
    )
    result = await db.execute(q)
    return result.scalar_one_or_none()
