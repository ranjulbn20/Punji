import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from database import get_db
from models import User, ImportJob, Transaction, MutualFund, Stock, StockTrade
from dependencies import get_current_user
from importers import detect_format, detect_xlsx_format, get_importer
from services.instrument_service import find_existing_instrument, build_instrument_from_dto
from services.market_service import get_nav_by_isin
from services.portfolio_service import compute_instrument_xirr

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
        fname = (file.filename or "").lower()
        if fname.endswith(".xlsx"):
            fmt = detect_xlsx_format(content)
        elif fname.endswith(".csv"):
            preview = content[:500].decode("utf-8", errors="replace")
            try:
                headers = next(csv.reader(io.StringIO(preview)))
                fmt = detect_format(headers, preview)
            except StopIteration:
                fmt = "generic"
        else:
            # Non-CSV, non-XLSX (e.g. PDF CAS statement)
            preview = content[:500].decode("utf-8", errors="replace")
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
                "stock_trade_count": len(h.stock_trades),
            }
            for h in holdings_dtos
        ]
        job.status = "preview_ready"
        job.preview_data = {"holdings": preview_data, "dtos_serialized": [
            {
                **d,
                "transactions": [
                    {"transaction_date": str(t.transaction_date), "transaction_type": t.transaction_type,
                     "amount": t.amount, "units": t.units, "price": t.price, "notes": t.notes}
                    for t in h.transactions
                ],
                "stock_trades": [
                    {"trade_date": str(st.trade_date), "trade_type": st.trade_type,
                     "quantity": st.quantity, "price": st.price, "amount": st.amount,
                     "exchange": st.exchange, "segment": st.segment, "trade_id": st.trade_id}
                    for st in h.stock_trades
                ],
            }
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
    total_stock_trades = sum(h.get("stock_trade_count", 0) for h in holdings)
    warnings = job.warnings or []
    if job.source_platform == "zerodha_tradebook":
        warnings = list(warnings) + ["Duplicate trades from overlapping date ranges will be skipped automatically."]
    return {
        "status": job.status,
        "holdings": holdings,
        "transactions": total_transactions,
        "stock_trades": total_stock_trades,
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

    created = updated = tx_created = stock_trades_created = 0

    # ── CAMS CAS: full replace ────────────────────────────────────────────────
    goal_map: dict[tuple, uuid.UUID] = {}
    if job.source_platform == "cams_cas":
        existing_q = select(MutualFund).where(
            MutualFund.user_id == user.id,
            MutualFund.is_active == True,
        )
        existing_mfs = (await db.execute(existing_q)).scalars().all()
        goal_map = {
            (mf.isin, mf.folio_number): mf.goal_id
            for mf in existing_mfs
            if mf.goal_id
        }
        for mf in existing_mfs:
            mf.is_active = False
        await db.flush()

    # ── Holdings snapshots: full replace ─────────────────────────────────────
    # Deactivate all active stocks before the loop; reactivate those in the snapshot.
    if job.source_platform in ("zerodha_holdings", "groww_stocks"):
        existing_stocks = (await db.execute(
            select(Stock).where(Stock.user_id == user.id, Stock.is_active == True)
        )).scalars().all()
        for s in existing_stocks:
            s.is_active = False
        await db.flush()

    # ── Enrich MF DTOs with live NAV from AMFI ───────────────────────────────
    for dto in dtos:
        if dto["instrument_type"] != "mutual_fund":
            continue
        isin = dto.get("metadata", {}).get("isin", "")
        if not isin:
            continue
        nav = await get_nav_by_isin(isin)
        if nav:
            meta = dto.setdefault("metadata", {})
            meta["scheme_code"] = nav["scheme_code"]
            meta["current_nav"] = nav["current_nav"]
            units = meta.get("units", 0)
            if units:
                dto["current_value"] = round(float(units) * nav["current_nav"], 2)

    for i, dto in enumerate(dtos):
        if i in skipped_indices:
            continue
        if confirmed_indices and i not in confirmed_indices:
            continue

        existing = await find_existing_instrument(db, user.id, dto)
        if existing:
            if job.source_platform != "zerodha_tradebook":
                existing.invested_amount = dto["invested_amount"]
                existing.current_value = dto["current_value"]
                if job.source_platform in ("zerodha_holdings", "groww_stocks") and dto["instrument_type"] == "stock":
                    meta = dto.get("metadata", {})
                    existing.quantity = meta.get("quantity", existing.quantity)
                    existing.avg_price = meta.get("average_price", existing.avg_price)
                    existing.current_price = meta.get("current_price", existing.current_price)
                    existing.is_active = True
            updated += 1
            instrument = existing
        else:
            if job.source_platform == "zerodha_tradebook":
                # Tradebook-only entry means this stock is fully sold (not in any current snapshot) — skip.
                continue
            instrument = build_instrument_from_dto(user.id, dto)
            db.add(instrument)
            await db.flush()
            created += 1

        if goal_map and dto["instrument_type"] == "mutual_fund":
            meta = dto.get("metadata", {})
            key = (meta.get("isin", ""), meta.get("folio_number", ""))
            if key in goal_map:
                instrument.goal_id = goal_map[key]

        instrument_type = dto["instrument_type"]

        # ── Stock trades (tradebook path) ─────────────────────────────────────
        if dto.get("stock_trades"):
            from datetime import date as date_type
            for st in dto["stock_trades"]:
                trade_date = date_type.fromisoformat(st["trade_date"])
                trade_id = st.get("trade_id", "")

                # Dedup: prefer trade_id match; fall back to stock+date+type+qty+price
                if trade_id:
                    dup_q = select(StockTrade).where(
                        StockTrade.stock_id == instrument.id,
                        StockTrade.trade_id == trade_id,
                    )
                else:
                    dup_q = select(StockTrade).where(
                        StockTrade.stock_id == instrument.id,
                        StockTrade.trade_date == trade_date,
                        StockTrade.trade_type == st["trade_type"],
                        StockTrade.quantity == st["quantity"],
                        StockTrade.price == st["price"],
                    )
                if (await db.execute(dup_q)).scalar_one_or_none():
                    continue

                db.add(StockTrade(
                    user_id=user.id,
                    stock_id=instrument.id,
                    trade_date=trade_date,
                    trade_type=st["trade_type"],
                    quantity=st["quantity"],
                    price=st["price"],
                    amount=st["amount"],
                    exchange=st.get("exchange", "NSE"),
                    segment=st.get("segment"),
                    trade_id=trade_id or None,
                    import_source=job.source_platform,
                ))
                stock_trades_created += 1

        # ── Generic transactions (MF / FD / PPF / NPS) ───────────────────────
        else:
            for tx in dto.get("transactions", []):
                from datetime import date as date_type
                tx_date = date_type.fromisoformat(tx["transaction_date"])
                tx_units = tx.get("units")
                tx_price = tx.get("price")
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
                if (await db.execute(dup_q)).scalar_one_or_none():
                    continue

                db.add(Transaction(
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
                ))
                tx_created += 1

    # Recompute XIRR for all affected stocks after a tradebook import.
    if job.source_platform == "zerodha_tradebook" and stock_trades_created > 0:
        await db.flush()
        affected_stocks = (await db.execute(
            select(Stock).where(Stock.user_id == user.id, Stock.is_active == True)
        )).scalars().all()
        for s in affected_stocks:
            xirr = await compute_instrument_xirr(db, s)
            if xirr is not None:
                s.xirr = xirr

    if user.onboarding_step < 1:
        user.onboarding_step = 1
    job.status = "completed"
    job.holdings_created = created
    job.holdings_updated = updated
    job.transactions_created = tx_created + stock_trades_created
    job.completed_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "holdings_created": created,
        "holdings_updated": updated,
        "transactions_created": tx_created,
        "stock_trades_created": stock_trades_created,
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
