from pydantic import BaseModel
import uuid
from datetime import date, datetime


class TransactionCreate(BaseModel):
    holding_id: uuid.UUID
    transaction_date: date
    transaction_type: str
    amount: int
    units: float | None = None
    price: float | None = None
    notes: str | None = None


class TransactionOut(BaseModel):
    id: uuid.UUID
    holding_id: uuid.UUID
    transaction_date: date
    transaction_type: str
    amount: int
    units: float | None
    price: float | None
    notes: str | None
    import_source: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
