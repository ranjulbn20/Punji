from pydantic import BaseModel, ConfigDict
import uuid
from datetime import datetime


class NewsHighlightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    instrument_type: str
    instrument_id: uuid.UUID
    holding_name: str
    symbol: str
    category: str
    headline: str
    link: str
    reason: str | None
    created_at: datetime
