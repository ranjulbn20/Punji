from pydantic import BaseModel
import uuid
from datetime import datetime


class HoldingCreate(BaseModel):
    instrument_type: str
    display_name: str
    asset_class: str
    invested_amount: int
    current_value: int
    metadata: dict = {}
    goal_id: uuid.UUID | None = None


class HoldingUpdate(BaseModel):
    display_name: str | None = None
    asset_class: str | None = None
    invested_amount: int | None = None
    current_value: int | None = None
    metadata: dict | None = None
    goal_id: uuid.UUID | None = None


class HoldingOut(BaseModel):
    id: uuid.UUID
    instrument_type: str
    display_name: str
    asset_class: str
    invested_amount: int
    current_value: int
    unrealised_pnl: int
    xirr: float | None
    metadata_: dict
    goal_id: uuid.UUID | None
    is_active: bool
    last_refreshed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_holding(cls, h):
        return cls(
            id=h.id,
            instrument_type=h.instrument_type,
            display_name=h.display_name,
            asset_class=h.asset_class,
            invested_amount=h.invested_amount,
            current_value=h.current_value,
            unrealised_pnl=h.unrealised_pnl,
            xirr=float(h.xirr) if h.xirr is not None else None,
            metadata_=h.metadata_,
            goal_id=h.goal_id,
            is_active=h.is_active,
            last_refreshed_at=h.last_refreshed_at,
            created_at=h.created_at,
        )
