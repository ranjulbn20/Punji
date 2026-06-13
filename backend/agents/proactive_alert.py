"""
Proactive Alert Agent — Gemini Flash.
Runs daily for each user, scores potential alerts, fires only >= 7.
"""
import json
import uuid
from datetime import date, datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import Goal, Alert, RiskProfile
from services.instrument_service import get_instruments_by_type
from services.portfolio_service import compute_allocation, compute_drift
from agents.news_intelligence import news_intelligence_node
from config import settings


async def _check_cooldown(db: AsyncSession, user_id: uuid.UUID, alert_type: str, days: int) -> bool:
    """Returns True if the user was notified within `days` days (cooldown active)."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(Alert).where(
            Alert.user_id == user_id,
            Alert.alert_type == alert_type,
            Alert.created_at >= cutoff,
        )
    )
    return result.scalar_one_or_none() is not None


async def _create_alert(db: AsyncSession, user_id: uuid.UUID, alert_type: str, severity: str,
                         title: str, message: str, reasoning: str, signal_score: int,
                         instrument_type: str | None = None, instrument_id: uuid.UUID | None = None,
                         goal_id: uuid.UUID | None = None, metadata: dict | None = None):
    alert = Alert(
        user_id=user_id,
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
        reasoning=reasoning,
        signal_score=signal_score,
        related_instrument_type=instrument_type,
        related_instrument_id=instrument_id,
        related_goal_id=goal_id,
        metadata_=metadata or {},
    )
    db.add(alert)


async def run_proactive_alerts_for_user(db: AsyncSession, user_id_str: str):
    user_id = uuid.UUID(user_id_str)
    alerts_created = 0

    # 1. Rebalancing drift
    drift = await compute_drift(db, user_id)
    if drift.get("has_risk_profile"):
        equity_drift = abs(drift.get("equity_drift", 0))
        base = min(equity_drift / 2, 5)
        score = base
        if equity_drift > 10:
            score += 2
        if not await _check_cooldown(db, user_id, "rebalancing_drift", 7):
            score += 1
        if await _check_cooldown(db, user_id, "rebalancing_drift", 7):
            score -= 3

        if score >= 7:
            await _create_alert(
                db, user_id, "rebalancing_drift", "significant",
                f"Rebalancing needed — equity drift {drift['equity_drift']:+.1f}%",
                f"Your equity allocation has drifted {drift['equity_drift']:+.1f}% from your target. "
                "Rebalancing now can reduce risk and lock in gains.",
                f"Drift score: {score:.1f}/10. Equity drift: {equity_drift:.1f}%.",
                int(score),
                metadata={"equity_drift": equity_drift, "urgency": drift.get("urgency", "medium")},
            )
            alerts_created += 1

    # 2. FD maturity alerts
    fds = await get_instruments_by_type(db, user_id, "fixed_deposit")
    for fd in fds:
        maturity_str = str(fd.maturity_date) if fd.maturity_date else None
        if not maturity_str:
            continue
        try:
            maturity = date.fromisoformat(maturity_str)
            days_left = (maturity - date.today()).days
        except ValueError:
            continue

        if days_left <= 7:
            score = 10
        elif days_left <= 14:
            score = 7
        elif days_left <= 30:
            score = 5
        else:
            continue

        if await _check_cooldown(db, user_id, "fd_maturity", 14):
            score -= 3

        if score >= 7:
            await _create_alert(
                db, user_id, "fd_maturity", "critical" if days_left <= 7 else "significant",
                f"FD maturing in {days_left} days — {fd.display_name}",
                f"Your Fixed Deposit with {fd.bank_name or 'your bank'} "
                f"matures on {maturity_str}. Plan your reinvestment strategy now.",
                f"Days to maturity: {days_left}. Signal score: {score}/10.",
                min(score, 10),
                instrument_type="fixed_deposit", instrument_id=fd.id,
                metadata={"days_to_maturity": days_left, "maturity_date": maturity_str},
            )
            alerts_created += 1

    # 3. Goal at risk
    goals_result = await db.execute(
        select(Goal).where(Goal.user_id == user_id, Goal.is_active == True)
    )
    for goal in goals_result.scalars().all():
        if not goal.success_probability:
            continue
        prob = float(goal.success_probability)
        if prob < 50:
            score = 10
        elif prob < 60:
            score = 8
        elif prob < 70:
            score = 7
        else:
            continue

        if await _check_cooldown(db, user_id, "goal_at_risk", 3):
            score -= 4

        if score >= 7:
            await _create_alert(
                db, user_id, "goal_at_risk", "critical" if prob < 50 else "significant",
                f"Goal at risk — {goal.name} ({prob:.0f}% success probability)",
                f"Your '{goal.name}' goal has only a {prob:.0f}% chance of success at current trajectory. "
                f"Consider increasing your monthly SIP by ₹{(goal.required_monthly_sip or 0) - goal.monthly_sip_allocated:,}.",
                f"Monte Carlo success probability: {prob:.0f}%. Required SIP: ₹{goal.required_monthly_sip or 0:,}.",
                min(score, 10),
                goal_id=goal.id,
                metadata={"success_probability": prob, "required_sip": goal.required_monthly_sip},
            )
            alerts_created += 1

    # 4. Concentration risk
    alloc = await compute_allocation(db, user_id)
    total = alloc.get("total_value", 0)
    if total > 0:
        for stock in await get_instruments_by_type(db, user_id, "stock"):
            pct = stock.current_value / total * 100
            if pct > 15:
                score = 9
            elif pct > 10:
                score = 7
            else:
                continue

            if await _check_cooldown(db, user_id, "concentration_risk", 30):
                score -= 3

            if score >= 7:
                await _create_alert(
                    db, user_id, "concentration_risk", "significant",
                    f"High concentration in {stock.display_name} ({pct:.1f}% of portfolio)",
                    f"{stock.display_name} represents {pct:.1f}% of your total portfolio. "
                    "Single-stock concentration above 10% increases risk significantly.",
                    f"Stock: {pct:.1f}% of portfolio. Threshold: 10%. Signal score: {score}/10.",
                    min(score, 10),
                    instrument_type="stock", instrument_id=stock.id,
                    metadata={"portfolio_pct": pct},
                )
                alerts_created += 1

    # 5. News alerts
    from agents.state import PunjiState
    news_state: PunjiState = {
        "user_id": user_id_str,
        "user_query": "",
        "run_type": "scheduled_daily",
        "reasoning_trace": [],
        "news_alerts": [],
        "new_memories": [],
        "alerts_to_create": [],
        "errors": [],
        "active_goals": [],
        "agent_memories": [],
        "current_agent": "news_intelligence",
    }
    news_state = await news_intelligence_node(news_state, db)

    for news_alert in news_state.get("news_alerts", []):
        category = news_alert.get("category", "monitor")
        score = 10 if category == "critical" else 7
        instrument_id = uuid.UUID(news_alert["instrument_id"]) if news_alert.get("instrument_id") else None
        instrument_type = news_alert.get("instrument_type", "stock")

        await _create_alert(
            db, user_id, "adverse_news",
            "critical" if category == "critical" else "significant",
            f"{'Critical' if category == 'critical' else 'Significant'} news: {news_alert['holding_name']}",
            f"{news_alert.get('headline', 'Important news detected')}. {news_alert.get('reason', '')}",
            f"News classified as '{category}'. Signal score: {score}/10.",
            score,
            instrument_type=instrument_type, instrument_id=instrument_id,
            metadata={"news_headline": news_alert.get("headline"), "category": category},
        )
        alerts_created += 1

    await db.commit()
    return alerts_created
