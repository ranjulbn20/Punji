from pydantic import BaseModel, EmailStr
import uuid
from datetime import datetime


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    google_id_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class RiskProfileRequest(BaseModel):
    drawdown_response: str  # 'sell_everything' | 'hold' | 'buy_more'


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    profile_picture_url: str | None
    onboarding_step: int
    auth_provider: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    user: UserOut


class RiskProfileOut(BaseModel):
    id: uuid.UUID
    drawdown_response: str
    risk_score: int | None
    risk_category: str | None
    target_equity_pct: float | None
    target_debt_pct: float | None
    target_gold_pct: float | None
    target_cash_pct: float | None

    model_config = {"from_attributes": True}
