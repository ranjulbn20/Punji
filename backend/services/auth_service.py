from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext

from config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict[str, Any]) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload["type"] = "access"
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def create_refresh_token(data: dict[str, Any]) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload["type"] = "refresh"
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])


def derive_risk_profile(drawdown_response: str) -> dict:
    profiles = {
        "sell_everything": {
            "risk_score": 2,
            "risk_category": "conservative",
            "target_equity_pct": 30.0,
            "target_debt_pct": 60.0,
            "target_gold_pct": 5.0,
            "target_cash_pct": 5.0,
        },
        "hold": {
            "risk_score": 5,
            "risk_category": "moderate",
            "target_equity_pct": 60.0,
            "target_debt_pct": 30.0,
            "target_gold_pct": 5.0,
            "target_cash_pct": 5.0,
        },
        "buy_more": {
            "risk_score": 8,
            "risk_category": "aggressive",
            "target_equity_pct": 80.0,
            "target_debt_pct": 10.0,
            "target_gold_pct": 5.0,
            "target_cash_pct": 5.0,
        },
    }
    return profiles.get(drawdown_response, profiles["hold"])
