import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import User, INSTRUMENT_MODEL_MAP
from schemas.holding import HoldingCreate, HoldingUpdate, HoldingOut
from dependencies import get_current_user
from services.instrument_service import (
    get_all_instruments, get_instrument_by_id, build_instrument_from_dto,
)

router = APIRouter(prefix="/api/holdings", tags=["holdings"])


@router.get("", response_model=list[HoldingOut])
async def list_holdings(
    instrument_type: str | None = Query(None),
    asset_class: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if instrument_type:
        instruments = await _list_by_type(db, user.id, instrument_type)
    else:
        instruments = await get_all_instruments(db, user.id)

    if asset_class:
        instruments = [h for h in instruments if h.asset_class == asset_class]

    return [HoldingOut.from_orm_holding(h) for h in instruments]


@router.get("/{holding_id}")
async def get_holding(
    holding_id: uuid.UUID,
    instrument_type: str = Query(..., description="Required: stock | mutual_fund | fixed_deposit | ppf | nps"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    h = await get_instrument_by_id(db, user.id, instrument_type, holding_id)
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")
    return HoldingOut.from_orm_holding(h)


@router.post("", response_model=HoldingOut, status_code=201)
async def create_holding(
    body: HoldingCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dto = body.model_dump()
    dto["metadata"] = dto.pop("metadata", {})
    instrument = build_instrument_from_dto(user.id, dto)
    db.add(instrument)
    if user.onboarding_step < 1:
        user.onboarding_step = 1
    await db.commit()
    await db.refresh(instrument)
    return HoldingOut.from_orm_holding(instrument)


@router.put("/{holding_id}")
async def update_holding(
    holding_id: uuid.UUID,
    body: HoldingUpdate,
    instrument_type: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    h = await get_instrument_by_id(db, user.id, instrument_type, holding_id)
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")

    updates = body.model_dump(exclude_unset=True)
    for field, val in updates.items():
        if hasattr(h, field):
            setattr(h, field, val)

    await db.commit()
    await db.refresh(h)
    return HoldingOut.from_orm_holding(h)


@router.delete("/{holding_id}")
async def delete_holding(
    holding_id: uuid.UUID,
    instrument_type: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    h = await get_instrument_by_id(db, user.id, instrument_type, holding_id)
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")
    h.is_active = False
    await db.commit()
    return {"success": True}


@router.post("/{holding_id}/refresh")
async def refresh_holding(
    holding_id: uuid.UUID,
    instrument_type: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from instruments import get_handler

    h = await get_instrument_by_id(db, user.id, instrument_type, holding_id)
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")

    handler = get_handler(instrument_type)
    if handler:
        new_value = await handler.fetch_current_value(h.metadata_)
        if new_value is not None:
            h.current_value = new_value
            h.last_refreshed_at = datetime.now(timezone.utc)
            await db.commit()

    return {"current_value": float(h.current_value), "last_refreshed_at": h.last_refreshed_at}


# ── Internal helper ───────────────────────────────────────────────────────────

async def _list_by_type(db, user_id, instrument_type: str):
    model = INSTRUMENT_MODEL_MAP.get(instrument_type)
    if not model:
        return []
    result = await db.execute(
        select(model).where(model.user_id == user_id, model.is_active == True)
    )
    return result.scalars().all()
