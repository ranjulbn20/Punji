"""
Proactive Alert Agent.
run_proactive_alerts_for_user() — daily, portfolio-level checks (rebalancing
drift, FD maturity, goal risk, concentration), scores potential alerts, fires
only >= 7.
run_market_signal_check_for_user() — separate, more frequent schedule
(every few hours during market hours): price+news signal engine, see its
own docstring below.
"""
import json
import uuid
from datetime import date, datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import Goal, Alert, RiskProfile
from services.benchmark_service import get_benchmark_context
from services.instrument_service import get_instruments_by_type
from services.market_service import get_multi_day_change, get_stock_industry, get_stock_price
from services.news_service import classify_news_signal
from services.opportunity_service import generate_opportunity, is_opportunity_worthy
from services.portfolio_service import compute_allocation, compute_drift
from services.signal_service import apply_context, compute_price_signal, fuse_signals
from config import settings

# Top N holdings by portfolio weight always get a news check, even with no
# price move — bad news on a large position can break before the price
# reacts (e.g. announced after market close, or over a weekend), and the
# position that matters most to the user shouldn't wait for a price crash
# to get investigated.
NEWS_ALWAYS_CHECK_TOP_N = 5


async def _check_cooldown(
    db: AsyncSession, user_id: uuid.UUID, alert_type: str, days: int,
    instrument_id: uuid.UUID | None = None,
) -> bool:
    """Returns True if the user was notified within `days` days (cooldown active).
    Scoped to a specific instrument when given — otherwise a cooldown on one
    stock would silently suppress alerts on every other stock of the same
    alert_type for the whole window."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    conditions = [
        Alert.user_id == user_id,
        Alert.alert_type == alert_type,
        Alert.created_at >= cutoff,
    ]
    if instrument_id is not None:
        conditions.append(Alert.related_instrument_id == instrument_id)
    result = await db.execute(select(Alert).where(*conditions))
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

    await db.commit()
    return alerts_created


async def run_market_signal_check_for_user(db: AsyncSession, user_id_str: str) -> int:
    """
    Market event signals — Phase 1 of the proactive signal engine
    (services/signal_service.py). Runs on its own, more frequent schedule
    (every few hours during market hours, see scheduler/jobs.py) — separate
    from run_proactive_alerts_for_user's once-daily portfolio-level checks,
    since a price move can't wait until tomorrow morning's alert run.

    Price signal (free) gates the expensive news+LLM step for most holdings,
    except the user's top NEWS_ALWAYS_CHECK_TOP_N positions by portfolio
    weight, which get a news check every cycle regardless — bad news on a
    large position can break before the price reacts. A price move alone is
    still alertable even with no news found (a stock can crash on broad
    market fear with no company-specific article at all).

    Benchmark comparison and portfolio weight (services/signal_service.py::
    apply_context) then moderate the result: a move mostly explained by the
    market/sector is downgraded and annotated rather than dropped, and a
    large position's alert is not under-weighted just because its % move
    looks moderate. Cooldown is per-instrument so one stock's alert can't
    suppress another's.

    Phase 3 — signals that clear a meaningfully higher bar than the plain
    informational alert (company-specific, high severity, high confidence —
    see opportunity_service.is_opportunity_worthy) additionally get routed
    through a recommendation + devil's-advocate pass, producing a second,
    distinct "signal_opportunity" alert. Detection and decision stay
    separate: the informational market_event alert always fires on its own;
    this is purely additive, and only for the rare high-conviction case.
    """
    user_id = uuid.UUID(user_id_str)
    alerts_created = 0

    stocks = [s for s in await get_instruments_by_type(db, user_id, "stock") if s.symbol]
    alloc = await compute_allocation(db, user_id)
    total_value = alloc.get("total_value", 0)

    rp_result = await db.execute(select(RiskProfile).where(RiskProfile.user_id == user_id))
    rp = rp_result.scalar_one_or_none()
    risk_profile = {
        "risk_category": rp.risk_category,
        "target_equity_pct": float(rp.target_equity_pct) if rp.target_equity_pct else None,
    } if rp else None

    always_check_ids = {
        s.id for s in sorted(stocks, key=lambda s: s.current_value, reverse=True)[:NEWS_ALWAYS_CHECK_TOP_N]
    }

    for stock in stocks:
        price_data = await get_stock_price(stock.symbol)
        change_1d = price_data.get("change_pct") if price_data else None
        change_5d = await get_multi_day_change(stock.symbol)
        price_signal = compute_price_signal(change_1d, change_5d)

        is_priority = stock.id in always_check_ids
        if not price_signal and not is_priority:
            continue

        if await _check_cooldown(db, user_id, "market_event", 1, instrument_id=stock.id):
            continue

        news_signal = await classify_news_signal(stock, stock.symbol)
        signal = fuse_signals(price_signal, news_signal)
        if not signal:
            continue

        benchmark_context = {}
        if change_1d is not None:
            industry = await get_stock_industry(stock.symbol)
            benchmark_context = await get_benchmark_context(industry, change_1d)

        portfolio_weight = (float(stock.current_value) / total_value * 100) if total_value else None
        signal = apply_context(signal, benchmark_context, portfolio_weight)

        direction = signal["direction"]
        trend = signal.get("trend")
        severity = signal["severity"]
        emoji = "🔴" if direction == "negative" else "🟢" if direction == "positive" else "🟡"
        score = 9 if severity == "high" else 7

        move_desc = f"{change_1d:+.1f}% today" if change_1d is not None else "a notable move"
        if news_signal:
            message = f"{news_signal['reason']} ({news_signal['headline']})"
        else:
            message = f"{stock.display_name} moved {move_desc} with no specific news identified."
        if signal["market_context"] == "broad_based":
            message += " This appears to track the broader market/sector rather than a company-specific event."
        if trend and trend != direction:
            message += f" Today's move is {direction}, but the 5-day trend remains {trend}."

        await _create_alert(
            db, user_id, "market_event",
            "critical" if severity == "high" else "significant",
            f"{emoji} {stock.display_name} — {move_desc}",
            message,
            f"Signals: {', '.join(signal['signal_types'])}. Confidence: {signal['confidence']:.2f}. "
            f"Market context: {signal['market_context']}. Evidence: {'; '.join(signal['evidence'])}.",
            score,
            instrument_type="stock", instrument_id=stock.id,
            metadata={
                "direction": direction,
                "trend": trend,
                "change_1d_pct": change_1d,
                "change_5d_pct": change_5d,
                "signal_types": signal["signal_types"],
                "confidence": signal["confidence"],
                "market_context": signal["market_context"],
                "portfolio_weight_pct": portfolio_weight,
                "benchmark": benchmark_context,
                "news_link": news_signal["link"] if news_signal else None,
            },
        )
        alerts_created += 1

        if is_opportunity_worthy(signal) and not await _check_cooldown(
            db, user_id, "signal_opportunity", 3, instrument_id=stock.id
        ):
            result = await generate_opportunity(stock, signal, risk_profile)
            if result:
                _create_opportunity_alert(db, stock, signal, result)
                alerts_created += 1

    await db.commit()
    return alerts_created


def _create_opportunity_alert(db: AsyncSession, stock, signal: dict, result: dict) -> None:
    """Builds and stages the signal_opportunity Alert from a proposal+critique
    pair. Deterministic templating, not another LLM call — the critique's
    overall rating decides how much weight it gets in the message, mirroring
    agents/orchestrator.py::synthesise_response's severity-weighting for the
    chat pipeline's proposal+critique pairs."""
    proposal = result["proposal"]
    critique = result["critique"]
    critique_overall = critique.get("overall", "not_applicable")
    action = proposal.get("action", "hold")

    if critique_overall == "critical":
        headline = "Signal detected, but proceed with caution"
        message = (
            f"{proposal.get('reasoning', '')} However, our risk review found a critical concern: "
            f"{critique.get('strongest_concern', '')}. Consider holding off."
        )
    elif critique_overall == "moderate":
        headline = f"Consider reviewing: {action} {stock.display_name}"
        message = f"{proposal.get('reasoning', '')} That said, {critique.get('strongest_concern', '')}"
    else:
        headline = f"Consider reviewing: {action} {stock.display_name}"
        message = proposal.get("reasoning", "")

    emoji = "🟢" if signal["direction"] == "positive" else "🔴"
    severity = "critical" if critique_overall == "critical" else "significant"
    score = 6 if critique_overall == "critical" else 8

    db.add(Alert(
        user_id=stock.user_id,
        alert_type="signal_opportunity",
        severity=severity,
        title=f"{emoji} {headline}",
        message=message,
        reasoning=f"Proposal: {action} ₹{proposal.get('amount_inr', 0):,} ({proposal.get('timeline', '')}). "
        f"Devil's advocate: {critique_overall}. {critique.get('strongest_concern', '')}",
        signal_score=score,
        related_instrument_type="stock",
        related_instrument_id=stock.id,
        metadata_={
            "proposal": proposal,
            "critique": critique,
            "signal_direction": signal["direction"],
            "signal_confidence": signal["confidence"],
        },
    ))
