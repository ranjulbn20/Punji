"""Goal Tracker Agent — Monte Carlo simulation, goal progress."""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from agents.state import PunjiState
from models import Goal
from services.portfolio_service import run_monte_carlo_for_goal


async def goal_tracker_node(state: PunjiState, db: AsyncSession) -> PunjiState:
    user_id = uuid.UUID(state["user_id"])

    result = await db.execute(select(Goal).where(Goal.user_id == user_id, Goal.is_active == True))
    goals = result.scalars().all()

    analysis = []
    for goal in goals:
        if not goal.success_probability:
            await run_monte_carlo_for_goal(db, goal, user_id)
            await db.refresh(goal)

        trajectory = "on_track"
        if goal.success_probability and goal.success_probability < 60:
            trajectory = "off_track"
        elif goal.success_probability and goal.success_probability < 75:
            trajectory = "at_risk"

        analysis.append({
            "id": str(goal.id),
            "name": goal.name,
            "target_amount": goal.target_amount,
            "success_probability": float(goal.success_probability) if goal.success_probability else None,
            "trajectory": trajectory,
            "required_monthly_sip": goal.required_monthly_sip,
        })

    state["goal_analysis"] = {"goals": analysis}
    state["reasoning_trace"] = state.get("reasoning_trace", []) + [
        f"GoalTracker: {len(goals)} goals analysed. "
        + (f"At-risk goals: {[g['name'] for g in analysis if g['trajectory'] != 'on_track']}" if analysis else "No goals.")
    ]
    return state
