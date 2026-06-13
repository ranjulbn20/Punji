from pydantic import BaseModel
import uuid
from datetime import date, datetime


class TransactionCreate(BaseModel):
    instrument_type: str
    instrument_id: uuid.UUID
    transaction_date: date
    transaction_type: str
    amount: float
    units: float | None = None
    price: float | None = None
    notes: str | None = None


class TransactionOut(BaseModel):
    id: uuid.UUID
    instrument_type: str
    instrument_id: uuid.UUID
    transaction_date: date
    transaction_type: str
    amount: float
    units: float | None
    price: float | None
    notes: str | None
    import_source: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
