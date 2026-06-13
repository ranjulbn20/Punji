from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import uuid

from database import get_db
from models import User, Alert
from schemas.agent import AlertFeedbackRequest
from dependencies import get_current_user

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(
    is_read: bool | None = None,
    alert_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Alert).where(Alert.user_id == user.id)
    if is_read is not None:
        q = q.where(Alert.is_read == is_read)
    if alert_type:
        q = q.where(Alert.alert_type == alert_type)
    q = q.order_by(Alert.is_read, Alert.created_at.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    alerts = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "alert_type": a.alert_type,
            "severity": a.severity,
            "title": a.title,
            "message": a.message,
            "reasoning": a.reasoning,
            "signal_score": a.signal_score,
            "is_read": a.is_read,
            "user_feedback": a.user_feedback,
            "related_instrument_id": str(a.related_instrument_id) if a.related_instrument_id else None,
            "related_instrument_type": a.related_instrument_type,
            "created_at": a.created_at,
        }
        for a in alerts
    ]


@router.put("/{alert_id}/read")
async def mark_read(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await db.execute(
        update(Alert).where(Alert.id == alert_id, Alert.user_id == user.id).values(is_read=True)
    )
    await db.commit()
    return {"success": True}


@router.put("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        update(Alert).where(Alert.user_id == user.id, Alert.is_read == False).values(is_read=True)
    )
    await db.commit()
    return {"updated_count": result.rowcount}


@router.post("/{alert_id}/feedback")
async def alert_feedback(
    alert_id: uuid.UUID,
    body: AlertFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    valid = {"helpful", "not_helpful", "already_knew", "not_relevant"}
    if body.feedback not in valid:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid feedback value")
    await db.execute(
        update(Alert)
        .where(Alert.id == alert_id, Alert.user_id == user.id)
        .values(user_feedback=body.feedback, is_read=True)
    )
    await db.commit()
    return {"success": True}
