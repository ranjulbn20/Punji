from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from datetime import date

from database import get_db
from models import User, Transaction, Holding
from schemas.transaction import TransactionCreate, TransactionOut
from dependencies import get_current_user

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionOut])
async def list_transactions(
    holding_id: uuid.UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Transaction).where(Transaction.user_id == user.id)
    if holding_id:
        q = q.where(Transaction.holding_id == holding_id)
    if from_date:
        q = q.where(Transaction.transaction_date >= from_date)
    if to_date:
        q = q.where(Transaction.transaction_date <= to_date)
    q = q.order_by(Transaction.transaction_date.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("", response_model=TransactionOut, status_code=201)
async def create_transaction(
    body: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    holding_check = await db.execute(
        select(Holding).where(Holding.id == body.holding_id, Holding.user_id == user.id)
    )
    if not holding_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Holding not found")

    tx = Transaction(user_id=user.id, **body.model_dump())
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx


@router.post("/bulk")
async def bulk_create_transactions(
    transactions: list[TransactionCreate],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    created, errors = [], []
    for i, body in enumerate(transactions):
        holding_check = await db.execute(
            select(Holding).where(Holding.id == body.holding_id, Holding.user_id == user.id)
        )
        if not holding_check.scalar_one_or_none():
            errors.append({"index": i, "error": "Holding not found"})
            continue
        tx = Transaction(user_id=user.id, **body.model_dump())
        db.add(tx)
        created.append(tx)

    await db.commit()
    return {"created_count": len(created), "errors": errors}
