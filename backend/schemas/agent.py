from pydantic import BaseModel
import uuid
from datetime import datetime


class ChatRequest(BaseModel):
    message: str
    conversation_id: uuid.UUID | None = None


class AlertFeedbackRequest(BaseModel):
    feedback: str  # 'helpful' | 'not_helpful' | 'already_knew' | 'not_relevant'


class AlertOut(BaseModel):
    id: uuid.UUID
    alert_type: str
    severity: str
    title: str
    message: str
    reasoning: str | None
    signal_score: int | None
    metadata_: dict
    is_read: bool
    is_acted_upon: bool
    user_feedback: str | None
    related_instrument_id: uuid.UUID | None
    related_instrument_type: str | None
    related_goal_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MemoryOut(BaseModel):
    id: uuid.UUID
    memory_type: str
    content: str
    confidence: float
    times_referenced: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ScenarioRequest(BaseModel):
    scenario_name: str
    assumption_changes: dict
    goal_id: uuid.UUID | None = None
