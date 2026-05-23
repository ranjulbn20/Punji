from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
import numpy as np
from datetime import date

from database import get_db
from models import User, Goal
from schemas.agent import ScenarioRequest
from dependencies import get_current_user

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


@router.post("/simulate")
async def simulate_scenario(
    body: ScenarioRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    changes = body.assumption_changes
    eq_return = changes.get("equity_return_pct", 12) / 100
    debt_return = changes.get("debt_return_pct", 7) / 100
    extra_sip = changes.get("additional_monthly_sip", 0)

    if body.goal_id:
        result = await db.execute(select(Goal).where(Goal.id == body.goal_id, Goal.user_id == user.id))
        goals = [result.scalar_one_or_none()]
        if not goals[0]:
            raise HTTPException(status_code=404, detail="Goal not found")
    else:
        result = await db.execute(select(Goal).where(Goal.user_id == user.id, Goal.is_active == True))
        goals = result.scalars().all()

    baseline_results = []
    scenario_results = []

    for goal in goals:
        months = (goal.target_date.year - date.today().year) * 12 + (goal.target_date.month - date.today().month)
        if months <= 0:
            continue
        target_rupees = goal.target_amount / 100
        sip = goal.monthly_sip_allocated

        def _simulate(monthly_mean: float, extra: int = 0, n: int = 500) -> dict:
            rng = np.random.default_rng()
            finals = []
            for _ in range(n):
                c = 0.0
                for _ in range(months):
                    r = rng.normal(monthly_mean, 0.18 / np.sqrt(12))
                    c = c * (1 + r) + sip + extra
                finals.append(c)
            finals = sorted(finals)
            success = sum(1 for v in finals if v >= target_rupees) / n
            return {
                "success_probability": round(success * 100, 1),
                "p50_corpus": int(finals[n // 2] * 100),
            }

        baseline = _simulate(0.12 / 12)
        scenario = _simulate(eq_return / 12, extra_sip)

        baseline_results.append({"goal_name": goal.name, **baseline})
        scenario_results.append({
            "goal_name": goal.name,
            **scenario,
            "probability_change": round(scenario["success_probability"] - baseline["success_probability"], 1),
        })

    return {
        "scenario_name": body.scenario_name,
        "baseline": baseline_results,
        "scenario": scenario_results,
        "assumption_changes": changes,
    }
