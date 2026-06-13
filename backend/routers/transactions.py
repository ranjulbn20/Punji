from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from datetime import date

from database import get_db
from models import User, Transaction
from dependencies import get_current_user
from services.instrument_service import get_instrument_by_id

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("")
async def list_transactions(
    instrument_id: uuid.UUID | None = None,
    instrument_type: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Transaction).where(Transaction.user_id == user.id)
    if instrument_id:
        q = q.where(Transaction.instrument_id == instrument_id)
    if instrument_type:
        q = q.where(Transaction.instrument_type == instrument_type)
    if from_date:
        q = q.where(Transaction.transaction_date >= from_date)
    if to_date:
        q = q.where(Transaction.transaction_date <= to_date)
    q = q.order_by(Transaction.transaction_date.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    txns = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "instrument_type": t.instrument_type,
            "instrument_id": str(t.instrument_id),
            "transaction_date": str(t.transaction_date),
            "transaction_type": t.transaction_type,
            "amount": float(t.amount),
            "units": float(t.units) if t.units is not None else None,
            "price": float(t.price) if t.price is not None else None,
            "notes": t.notes,
            "import_source": t.import_source,
        }
        for t in txns
    ]


@router.post("", status_code=201)
async def create_transaction(
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    instrument_type = body.get("instrument_type")
    instrument_id = body.get("instrument_id")
    if not instrument_type or not instrument_id:
        raise HTTPException(status_code=400, detail="instrument_type and instrument_id are required")

    instrument = await get_instrument_by_id(db, user.id, instrument_type, uuid.UUID(instrument_id))
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")

    tx = Transaction(
        user_id=user.id,
        instrument_type=instrument_type,
        instrument_id=instrument.id,
        transaction_date=date.fromisoformat(body["transaction_date"]),
        transaction_type=body["transaction_type"],
        amount=body["amount"],
        units=body.get("units"),
        price=body.get("price"),
        notes=body.get("notes"),
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return {"id": str(tx.id), "instrument_type": tx.instrument_type, "instrument_id": str(tx.instrument_id)}
