from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import uuid

from database import get_db
from models import User, Holding
from schemas.holding import HoldingCreate, HoldingUpdate, HoldingOut
from dependencies import get_current_user

router = APIRouter(prefix="/api/holdings", tags=["holdings"])


@router.get("", response_model=list[HoldingOut])
async def list_holdings(
    instrument_type: str | None = None,
    asset_class: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Holding).where(Holding.user_id == user.id, Holding.is_active == True)
    if instrument_type:
        q = q.where(Holding.instrument_type == instrument_type)
    if asset_class:
        q = q.where(Holding.asset_class == asset_class)
    result = await db.execute(q)
    holdings = result.scalars().all()
    return [HoldingOut.from_orm_holding(h) for h in holdings]


@router.get("/{holding_id}")
async def get_holding(
    holding_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Holding).where(Holding.id == holding_id, Holding.user_id == user.id)
    )
    h = result.scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")
    return HoldingOut.from_orm_holding(h)


@router.post("", response_model=HoldingOut, status_code=201)
async def create_holding(
    body: HoldingCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    h = Holding(
        user_id=user.id,
        instrument_type=body.instrument_type,
        display_name=body.display_name,
        asset_class=body.asset_class,
        invested_amount=body.invested_amount,
        current_value=body.current_value,
        metadata_=body.metadata,
        goal_id=body.goal_id,
    )
    db.add(h)
    if user.onboarding_step < 1:
        user.onboarding_step = 1
    await db.commit()
    await db.refresh(h)
    return HoldingOut.from_orm_holding(h)


@router.put("/{holding_id}", response_model=HoldingOut)
async def update_holding(
    holding_id: uuid.UUID,
    body: HoldingUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Holding).where(Holding.id == holding_id, Holding.user_id == user.id)
    )
    h = result.scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")

    for field, val in body.model_dump(exclude_unset=True).items():
        if field == "metadata":
            h.metadata_ = val
        else:
            setattr(h, field, val)

    await db.commit()
    await db.refresh(h)
    return HoldingOut.from_orm_holding(h)


@router.delete("/{holding_id}")
async def delete_holding(
    holding_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Holding).where(Holding.id == holding_id, Holding.user_id == user.id)
    )
    h = result.scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")
    h.is_active = False
    await db.commit()
    return {"success": True}


@router.post("/{holding_id}/refresh")
async def refresh_holding(
    holding_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from instruments import get_handler
    from datetime import datetime, timezone

    result = await db.execute(
        select(Holding).where(Holding.id == holding_id, Holding.user_id == user.id)
    )
    h = result.scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")

    handler = get_handler(h.instrument_type)
    if handler:
        new_value = await handler.fetch_current_value(h.metadata_)
        if new_value is not None:
            h.current_value = new_value
            h.last_refreshed_at = datetime.now(timezone.utc)
            await db.commit()

    return {"current_value": h.current_value, "last_refreshed_at": h.last_refreshed_at}
