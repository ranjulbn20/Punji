"""
Financial mathematics engine. Pure Python, no LLM dependency.
All monetary values stored in rupees (Numeric 15,2).
"""
from datetime import date, datetime, timezone
from typing import Optional
import numpy as np
from scipy import optimize
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import Transaction, Goal, RiskProfile, PortfolioSnapshot
from services.instrument_service import get_all_instruments
from config import settings


# ─── XIRR ────────────────────────────────────────────────────────────────────

def compute_xirr(cashflows: list[tuple[date, float]]) -> Optional[float]:
    """
    Compute XIRR from a list of (date, amount) tuples.
    Sign convention: positive = money out of pocket (buys/deposits),
                     negative = money received (sells/maturities).
    Returns annualised rate as decimal (e.g. 0.142 = 14.2%) or None.
    """
    if len(cashflows) < 2:
        return None

    dates = [cf[0] for cf in cashflows]
    amounts = [cf[1] for cf in cashflows]
    base_date = dates[0]
    day_offsets = [(d - base_date).days for d in dates]

    if max(day_offsets) < 30:
        return None  # Too short

    def npv(rate: float) -> float:
        return sum(a / ((1 + rate) ** (t / 365)) for a, t in zip(amounts, day_offsets))

    try:
        result = optimize.brentq(npv, -0.999, 100.0, maxiter=200)
        return round(result * 100, 2)  # Return as percentage
    except (ValueError, RuntimeError):
        return None


async def compute_instrument_xirr(db: AsyncSession, instrument) -> Optional[float]:
    result = await db.execute(
        select(Transaction)
        .where(
            Transaction.instrument_type == instrument.instrument_type,
            Transaction.instrument_id == instrument.id,
        )
        .order_by(Transaction.transaction_date)
    )
    transactions = result.scalars().all()
    if not transactions:
        return None

    cashflows = [(tx.transaction_date, float(tx.amount)) for tx in transactions]
    cashflows.append((date.today(), -float(instrument.current_value)))
    return compute_xirr(cashflows)


# Keep old name as alias for call sites not yet updated
compute_holding_xirr = compute_instrument_xirr


async def compute_portfolio_xirr(db: AsyncSession, user_id) -> Optional[float]:
    result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.transaction_date)
    )
    transactions = result.scalars().all()

    instruments = await get_all_instruments(db, user_id)
    total_current = sum(float(h.current_value) for h in instruments)

    if not transactions or total_current == 0:
        return None

    cashflows = [(tx.transaction_date, float(tx.amount)) for tx in transactions]
    cashflows.append((date.today(), -total_current))
    return compute_xirr(cashflows)


# ─── ALLOCATION ENGINE ────────────────────────────────────────────────────────

async def compute_allocation(db: AsyncSession, user_id) -> dict:
    holdings = await get_all_instruments(db, user_id)

    buckets = {"equity": 0, "debt": 0, "gold": 0, "cash": 0, "real_estate": 0, "alternative": 0}
    total = 0

    for h in holdings:
        buckets[h.asset_class] = buckets.get(h.asset_class, 0) + float(h.current_value)
        total += float(h.current_value)

    if total == 0:
        return {k: 0.0 for k in buckets} | {"total_value": 0.0}

    pcts = {k: round(v / total * 100, 2) for k, v in buckets.items()}
    return pcts | {"total_value": total, "by_class": buckets}


async def compute_drift(db: AsyncSession, user_id) -> dict:
    rp_result = await db.execute(select(RiskProfile).where(RiskProfile.user_id == user_id))
    rp = rp_result.scalar_one_or_none()
    alloc = await compute_allocation(db, user_id)

    if not rp:
        return {"has_risk_profile": False}

    equity_drift = round(alloc.get("equity", 0) - float(rp.target_equity_pct or 0), 2)
    debt_drift = round(alloc.get("debt", 0) - float(rp.target_debt_pct or 0), 2)
    gold_drift = round(alloc.get("gold", 0) - float(rp.target_gold_pct or 0), 2)

    needs_rebalancing = abs(equity_drift) > 5 or abs(debt_drift) > 5

    return {
        "has_risk_profile": True,
        "equity_drift": equity_drift,
        "debt_drift": debt_drift,
        "gold_drift": gold_drift,
        "needs_rebalancing": needs_rebalancing,
        "urgency": "high" if abs(equity_drift) > 10 else ("medium" if needs_rebalancing else "low"),
    }


# ─── BENCHMARK COMPARISON ─────────────────────────────────────────────────────

async def compute_benchmark_comparison(db: AsyncSession, user_id) -> dict:
    try:
        import yfinance as yf
        result = await db.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.transaction_date)
        )
        transactions = result.scalars().all()
        if not transactions:
            return {}

        first_date = transactions[0].transaction_date
        nifty50 = yf.Ticker("^NSEI")
        nifty500 = yf.Ticker("^NSMIDCP")

        hist50 = nifty50.history(start=first_date.isoformat(), period="1y")
        hist500 = nifty500.history(start=first_date.isoformat(), period="1y")

        def _1y_return(hist) -> Optional[float]:
            if hist.empty or len(hist) < 2:
                return None
            first = hist["Close"].iloc[0]
            last = hist["Close"].iloc[-1]
            return round((last - first) / first * 100, 2)

        return {
            "nifty50_xirr": _1y_return(hist50),
            "nifty500_xirr": _1y_return(hist500),
        }
    except Exception:
        return {}


# ─── RISK METRICS ─────────────────────────────────────────────────────────────

async def compute_risk_metrics(db: AsyncSession, user_id) -> dict:
    result = await db.execute(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == user_id)
        .order_by(PortfolioSnapshot.snapshot_date)
    )
    snapshots = result.scalars().all()

    if len(snapshots) < 3:
        return {}

    values = np.array([s.total_value for s in snapshots], dtype=float)
    monthly_returns = np.diff(values) / values[:-1]

    risk_free_rate = settings.rbi_repo_rate / 100

    # Sharpe ratio
    if monthly_returns.std() == 0:
        sharpe = None
    else:
        ann_return = np.mean(monthly_returns) * 12
        ann_std = monthly_returns.std() * np.sqrt(12)
        sharpe = round((ann_return - risk_free_rate) / ann_std, 2)

    # Max drawdown
    peak = values[0]
    max_drawdown = 0.0
    for v in values:
        if v > peak:
            peak = v
        drawdown = (peak - v) / peak
        max_drawdown = max(max_drawdown, drawdown)

    # Volatility (annualised)
    volatility = round(float(monthly_returns.std() * np.sqrt(12) * 100), 2)

    return {
        "sharpe_ratio": sharpe,
        "max_drawdown": round(max_drawdown * 100, 2),
        "volatility": volatility,
    }


# ─── PORTFOLIO SUMMARY ────────────────────────────────────────────────────────

async def compute_portfolio_summary(db: AsyncSession, user_id) -> dict:
    holdings = await get_all_instruments(db, user_id)

    total_value = sum(float(h.current_value) for h in holdings)
    total_invested = sum(float(h.invested_amount) for h in holdings)
    total_pnl = total_value - total_invested
    total_pnl_pct = round(total_pnl / total_invested * 100, 2) if total_invested else 0

    portfolio_xirr = await compute_portfolio_xirr(db, user_id)
    allocation = await compute_allocation(db, user_id)
    drift = await compute_drift(db, user_id)
    benchmarks = await compute_benchmark_comparison(db, user_id)
    risk_metrics = await compute_risk_metrics(db, user_id)

    return {
        "total_value": total_value,
        "total_invested": total_invested,
        "total_pnl_amount": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "portfolio_xirr": portfolio_xirr,
        "allocation": allocation,
        "drift": drift,
        "benchmarks": benchmarks,
        "risk_metrics": risk_metrics,
    }


# ─── MONTE CARLO ──────────────────────────────────────────────────────────────

async def run_monte_carlo_for_goal(db: AsyncSession, goal: Goal, user_id) -> None:
    """Run 1,000-simulation Monte Carlo and update goal simulation fields."""
    all_instruments = await get_all_instruments(db, user_id)
    goal_holdings = [h for h in all_instruments if h.goal_id == goal.id]

    if not goal_holdings:
        goal_holdings = all_instruments

    # Determine asset mix of linked holdings
    total_val = sum(h.current_value for h in goal_holdings) or 1
    equity_pct = sum(h.current_value for h in goal_holdings if h.asset_class == "equity") / total_val
    debt_pct = 1 - equity_pct

    months_to_goal = (
        (goal.target_date.year - date.today().year) * 12
        + (goal.target_date.month - date.today().month)
    )
    if months_to_goal <= 0:
        return

    n_simulations = 1000
    current_corpus = sum(float(h.current_value) for h in goal_holdings)
    monthly_sip = goal.monthly_sip_allocated

    equity_mean_monthly = 0.12 / 12
    equity_std_monthly = 0.18 / np.sqrt(12)
    debt_mean_monthly = 0.07 / 12
    debt_std_monthly = 0.03 / np.sqrt(12)

    rng = np.random.default_rng(42)
    final_values = []

    for _ in range(n_simulations):
        corpus = current_corpus
        for _ in range(months_to_goal):
            eq_return = rng.normal(equity_mean_monthly, equity_std_monthly)
            db_return = rng.normal(debt_mean_monthly, debt_std_monthly)
            monthly_return = equity_pct * eq_return + debt_pct * db_return
            corpus = corpus * (1 + monthly_return) + monthly_sip
        final_values.append(corpus)

    final_values_sorted = sorted(final_values)
    target = float(goal.target_amount)

    success_count = sum(1 for v in final_values if v >= target)
    success_prob = round(success_count / n_simulations * 100, 1)

    # Required SIP for 90% success (binary search)
    def _success_rate(sip):
        vals = []
        for _ in range(500):
            c = current_corpus
            for _ in range(months_to_goal):
                eq_r = rng.normal(equity_mean_monthly, equity_std_monthly)
                db_r = rng.normal(debt_mean_monthly, debt_std_monthly)
                r = equity_pct * eq_r + debt_pct * db_r
                c = c * (1 + r) + sip
            vals.append(c)
        return sum(1 for v in vals if v >= target) / 500

    lo, hi = 0, 500000
    for _ in range(20):
        mid = (lo + hi) / 2
        if _success_rate(mid) >= 0.9:
            hi = mid
        else:
            lo = mid
    required_sip = int(hi)

    n = len(final_values_sorted)
    goal.success_probability = success_prob
    goal.required_monthly_sip = required_sip
    goal.projected_corpus_p10 = int(final_values_sorted[int(n * 0.1)] * 100)
    goal.projected_corpus_p50 = int(final_values_sorted[int(n * 0.5)] * 100)
    goal.projected_corpus_p90 = int(final_values_sorted[int(n * 0.9)] * 100)
    goal.last_simulation_at = datetime.now(timezone.utc)
    await db.commit()
