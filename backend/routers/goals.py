from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from database import get_db
from models import User, Goal
from schemas.goal import GoalCreate, GoalUpdate, GoalOut
from dependencies import get_current_user

router = APIRouter(prefix="/api/goals", tags=["goals"])


@router.get("", response_model=list[GoalOut])
async def list_goals(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Goal).where(Goal.user_id == user.id, Goal.is_active == True))
    return result.scalars().all()


@router.post("", response_model=GoalOut, status_code=201)
async def create_goal(
    body: GoalCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    goal = Goal(user_id=user.id, **body.model_dump())
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return goal


@router.get("/{goal_id}", response_model=GoalOut)
async def get_goal(
    goal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.put("/{goal_id}", response_model=GoalOut)
async def update_goal(
    goal_id: uuid.UUID,
    body: GoalUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(goal, field, val)
    await db.commit()
    await db.refresh(goal)
    return goal


@router.delete("/{goal_id}")
async def delete_goal(
    goal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    goal.is_active = False
    await db.commit()
    return {"success": True}


@router.get("/{goal_id}/simulation")
async def get_simulation(
    goal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    from datetime import date
    months_to_goal = (goal.target_date.year - date.today().year) * 12 + (goal.target_date.month - date.today().month)

    trajectory = "on_track"
    if goal.success_probability is not None:
        if goal.success_probability < 60:
            trajectory = "off_track"
        elif goal.success_probability < 75:
            trajectory = "at_risk"

    return {
        "success_probability": float(goal.success_probability) if goal.success_probability else None,
        "required_monthly_sip": goal.required_monthly_sip,
        "projected_corpus_p10": goal.projected_corpus_p10,
        "projected_corpus_p50": goal.projected_corpus_p50,
        "projected_corpus_p90": goal.projected_corpus_p90,
        "months_to_goal": max(months_to_goal, 0),
        "current_trajectory": trajectory,
        "last_simulation_at": goal.last_simulation_at,
    }


@router.post("/{goal_id}/simulate")
async def trigger_simulation(
    goal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from services.portfolio_service import run_monte_carlo_for_goal
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    await run_monte_carlo_for_goal(db, goal, user.id)
    return {"success": True}
