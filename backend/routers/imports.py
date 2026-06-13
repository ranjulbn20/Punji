import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import User, ImportJob, Transaction
from dependencies import get_current_user
from importers import detect_format, get_importer
from services.instrument_service import find_existing_instrument, build_instrument_from_dto

router = APIRouter(prefix="/api/imports", tags=["imports"])


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    source_platform: str = Form("generic"),
    password: str = Form(""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    content = await file.read()

    # Detect format
    fmt = source_platform
    if source_platform in ("auto", "generic", "other"):
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
        holdings_dtos = await importer.parse(content, file.filename or "upload.csv", password=password)
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
    holdings = preview.get("holdings", [])
    total_transactions = sum(h.get("transaction_count", 0) for h in holdings)
    warnings = job.warnings or []
    if job.source_platform == "zerodha_tradebook":
        warnings = list(warnings) + ["Duplicate transactions from overlapping date ranges will be skipped automatically."]
    return {
        "status": job.status,
        "holdings": holdings,
        "transactions": total_transactions,
        "warnings": warnings,
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

        # Dedup: find existing instrument in the typed table
        existing = await find_existing_instrument(db, user.id, dto)
        if existing:
            # Tradebook imports only have partial history — never overwrite snapshot amounts
            if job.source_platform != "zerodha_tradebook":
                existing.invested_amount = dto["invested_amount"]
                existing.current_value = dto["current_value"]
            updated += 1
            instrument = existing
        else:
            instrument = build_instrument_from_dto(user.id, dto)
            db.add(instrument)
            await db.flush()
            created += 1

        instrument_type = dto["instrument_type"]

        for tx in dto.get("transactions", []):
            from datetime import date
            tx_date = date.fromisoformat(tx["transaction_date"])
            tx_units = tx.get("units")
            tx_price = tx.get("price")

            # Dedup: when notes carries a trade_id use it as the unique key;
            # otherwise match on date + type + units + price.
            tx_notes = tx.get("notes")
            tx_trade_id = tx_notes if (tx_notes and tx_notes.startswith("trade_id:")) else None

            dup_q = select(Transaction).where(
                Transaction.instrument_type == instrument_type,
                Transaction.instrument_id == instrument.id,
                Transaction.transaction_date == tx_date,
                Transaction.transaction_type == tx["transaction_type"],
            )
            if tx_trade_id:
                dup_q = dup_q.where(Transaction.notes == tx_trade_id)
            else:
                if tx_units is not None:
                    dup_q = dup_q.where(Transaction.units == tx_units)
                if tx_price is not None:
                    dup_q = dup_q.where(Transaction.price == tx_price)
            dup = await db.execute(dup_q)
            if dup.scalar_one_or_none():
                continue

            t = Transaction(
                user_id=user.id,
                instrument_type=instrument_type,
                instrument_id=instrument.id,
                transaction_date=tx_date,
                transaction_type=tx["transaction_type"],
                amount=tx["amount"],
                units=tx_units,
                price=tx_price,
                notes=tx_notes,
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


