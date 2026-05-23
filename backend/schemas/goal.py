from pydantic import BaseModel
import uuid
from datetime import date, datetime


class GoalCreate(BaseModel):
    name: str
    goal_type: str | None = None
    target_amount: int
    target_date: date
    monthly_sip_allocated: int = 0
    priority: int = 1


class GoalUpdate(BaseModel):
    name: str | None = None
    goal_type: str | None = None
    target_amount: int | None = None
    target_date: date | None = None
    monthly_sip_allocated: int | None = None
    priority: int | None = None


class GoalOut(BaseModel):
    id: uuid.UUID
    name: str
    goal_type: str | None
    target_amount: int
    target_date: date
    monthly_sip_allocated: int
    priority: int
    success_probability: float | None
    required_monthly_sip: int | None
    projected_corpus_p10: int | None
    projected_corpus_p50: int | None
    projected_corpus_p90: int | None
    last_simulation_at: datetime | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
