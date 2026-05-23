from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, timedelta

from database import get_db
from models import User, PortfolioSnapshot
from dependencies import get_current_user
from services.portfolio_service import (
    compute_portfolio_summary, compute_allocation, compute_drift,
    compute_benchmark_comparison, compute_risk_metrics,
)
from services.concentration_service import compute_concentration

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/summary")
async def portfolio_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from models import Alert
    summary = await compute_portfolio_summary(db, user.id)
    unread = await db.execute(
        select(Alert).where(Alert.user_id == user.id, Alert.is_read == False)
    )
    summary["unread_alerts_count"] = len(unread.scalars().all())
    return summary


@router.get("/allocation")
async def portfolio_allocation(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from models import RiskProfile, Holding
    alloc = await compute_allocation(db, user.id)
    drift = await compute_drift(db, user.id)

    rp_result = await db.execute(select(RiskProfile).where(RiskProfile.user_id == user.id))
    rp = rp_result.scalar_one_or_none()

    by_type_result = await db.execute(
        select(Holding).where(Holding.user_id == user.id, Holding.is_active == True)
    )
    holdings = by_type_result.scalars().all()
    total = sum(h.current_value for h in holdings) or 1

    by_instrument = {}
    for h in holdings:
        by_instrument[h.instrument_type] = by_instrument.get(h.instrument_type, 0) + h.current_value
    by_instrument_list = [
        {"instrument_type": k, "value": v, "pct": round(v / total * 100, 2)}
        for k, v in by_instrument.items()
    ]

    return {
        "current": alloc,
        "target": {
            "equity_pct": float(rp.target_equity_pct) if rp else None,
            "debt_pct": float(rp.target_debt_pct) if rp else None,
            "gold_pct": float(rp.target_gold_pct) if rp else None,
            "cash_pct": float(rp.target_cash_pct) if rp else None,
        } if rp else None,
        "drift": drift,
        "by_instrument_type": by_instrument_list,
    }


@router.get("/performance")
async def portfolio_performance(
    period: str = Query("1y", pattern="^(1m|3m|6m|1y|3y|all)$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    period_days = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "3y": 1095, "all": 99999}
    days = period_days.get(period, 365)
    from_date = date.today() - timedelta(days=days)

    result = await db.execute(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == user.id, PortfolioSnapshot.snapshot_date >= from_date)
        .order_by(PortfolioSnapshot.snapshot_date)
    )
    snapshots = result.scalars().all()

    chart_data = [
        {
            "date": str(s.snapshot_date),
            "portfolio_value": s.total_value,
            "nifty50_return": float(s.nifty50_return_1y) if s.nifty50_return_1y else None,
        }
        for s in snapshots
    ]

    benchmarks = await compute_benchmark_comparison(db, user.id)
    return {
        "chart_data": chart_data,
        "benchmarks": benchmarks,
        "period": period,
    }


@router.get("/concentration")
async def portfolio_concentration(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await compute_concentration(db, user.id)


@router.get("/snapshots")
async def portfolio_snapshots(
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(PortfolioSnapshot).where(PortfolioSnapshot.user_id == user.id)
    if from_date:
        q = q.where(PortfolioSnapshot.snapshot_date >= from_date)
    if to_date:
        q = q.where(PortfolioSnapshot.snapshot_date <= to_date)
    q = q.order_by(PortfolioSnapshot.snapshot_date)
    result = await db.execute(q)
    return [
        {
            "date": str(s.snapshot_date),
            "total_value": s.total_value,
            "equity_pct": float(s.equity_pct) if s.equity_pct else None,
            "debt_pct": float(s.debt_pct) if s.debt_pct else None,
        }
        for s in result.scalars().all()
    ]
