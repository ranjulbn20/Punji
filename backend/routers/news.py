from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import get_current_user
from models import User
from schemas.news import NewsHighlightOut
from services.news_service import get_news_highlights, refresh_news_highlights

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("", response_model=list[NewsHighlightOut])
async def list_news(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await get_news_highlights(db, user.id)


@router.post("/refresh", response_model=list[NewsHighlightOut])
async def refresh_news(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Re-fetch and re-classify news for the user's stock holdings. Triggered by the dashboard's refresh button."""
    return await refresh_news_highlights(db, user.id)
