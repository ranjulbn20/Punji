from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx

from database import get_db
from models import User, RiskProfile
from schemas.user import (
    RegisterRequest, LoginRequest, GoogleAuthRequest,
    RefreshRequest, LogoutRequest, RiskProfileRequest,
    TokenPair, UserOut, RiskProfileOut,
)
from services.auth_service import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    derive_risk_profile,
)
from services.market_service import refresh_mf_navs_bg, refresh_stock_prices_bg
from dependencies import get_current_user
from jose import JWTError

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenPair)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=body.email,
        full_name=body.full_name,
        password_hash=hash_password(body.password),
        auth_provider="email",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token_data = {"sub": str(user.id)}
    return TokenPair(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenPair)
async def login(body: LoginRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    background_tasks.add_task(refresh_mf_navs_bg, str(user.id))
    background_tasks.add_task(refresh_stock_prices_bg, str(user.id))
    token_data = {"sub": str(user.id)}
    return TokenPair(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        user=UserOut.model_validate(user),
    )


@router.post("/google")
async def google_auth(body: GoogleAuthRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": body.google_id_token},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    google_data = resp.json()
    google_user_id = google_data.get("sub")
    email = google_data.get("email")
    name = google_data.get("name")
    picture = google_data.get("picture")

    result = await db.execute(select(User).where(User.google_user_id == google_user_id))
    user = result.scalar_one_or_none()
    is_new = False

    if not user:
        existing = await db.execute(select(User).where(User.email == email))
        user = existing.scalar_one_or_none()
        if user:
            user.google_user_id = google_user_id
            user.auth_provider = "both"
        else:
            user = User(
                email=email,
                full_name=name,
                profile_picture_url=picture,
                google_user_id=google_user_id,
                auth_provider="google",
            )
            db.add(user)
            is_new = True

    await db.commit()
    await db.refresh(user)

    if not is_new:
        background_tasks.add_task(refresh_mf_navs_bg, str(user.id))
        background_tasks.add_task(refresh_stock_prices_bg, str(user.id))
    token_data = {"sub": str(user.id)}
    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "user": UserOut.model_validate(user),
        "is_new_user": is_new,
    }


@router.post("/refresh")
async def refresh(body: RefreshRequest):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return {"access_token": create_access_token({"sub": payload["sub"]})}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")


@router.post("/logout")
async def logout():
    # Stateless JWT — client drops the token; no server-side action needed
    return {"success": True}


@router.post("/onboarding/risk-profile", response_model=dict)
async def set_risk_profile(
    body: RiskProfileRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.drawdown_response not in ("sell_everything", "hold", "buy_more"):
        raise HTTPException(status_code=400, detail="Invalid drawdown_response")

    profile_data = derive_risk_profile(body.drawdown_response)

    result = await db.execute(select(RiskProfile).where(RiskProfile.user_id == user.id))
    rp = result.scalar_one_or_none()
    if rp:
        rp.drawdown_response = body.drawdown_response
        for k, v in profile_data.items():
            setattr(rp, k, v)
    else:
        rp = RiskProfile(user_id=user.id, drawdown_response=body.drawdown_response, **profile_data)
        db.add(rp)

    user.onboarding_step = max(user.onboarding_step, 2)
    await db.commit()
    await db.refresh(rp)

    return {
        "risk_profile": RiskProfileOut.model_validate(rp),
        "target_allocation": {
            "equity_pct": float(rp.target_equity_pct),
            "debt_pct": float(rp.target_debt_pct),
            "gold_pct": float(rp.target_gold_pct),
            "cash_pct": float(rp.target_cash_pct),
        },
    }


@router.get("/onboarding/status")
async def onboarding_status(user: User = Depends(get_current_user)):
    step_map = {
        0: "add_holdings",
        1: "complete_risk_profile",
        2: "explore_dashboard",
        3: "complete",
    }
    return {
        "onboarding_step": user.onboarding_step,
        "next_step": step_map.get(user.onboarding_step, "complete"),
        "is_complete": user.onboarding_step >= 3,
    }
