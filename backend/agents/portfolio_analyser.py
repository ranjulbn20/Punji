"""Portfolio Analyser Agent — pure Python, no LLM."""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from agents.state import PunjiState
from services.portfolio_service import (
    compute_allocation, compute_drift, compute_portfolio_xirr, compute_risk_metrics
)
from services.concentration_service import compute_concentration


async def portfolio_analyser_node(state: PunjiState, db: AsyncSession) -> PunjiState:
    user_id = uuid.UUID(state["user_id"])

    allocation = await compute_allocation(db, user_id)
    drift = await compute_drift(db, user_id)
    xirr = await compute_portfolio_xirr(db, user_id)
    risk_metrics = await compute_risk_metrics(db, user_id)
    concentration = await compute_concentration(db, user_id)

    report = {
        "allocation": allocation,
        "drift": drift,
        "portfolio_xirr": xirr,
        "risk_metrics": risk_metrics,
    }

    state["allocation_report"] = report
    state["concentration_report"] = concentration
    state["reasoning_trace"] = state.get("reasoning_trace", []) + [
        f"PortfolioAnalyser: allocation computed. Equity {allocation.get('equity', 0):.1f}%, "
        f"drift {drift.get('equity_drift', 0):+.1f}%. XIRR {xirr}%."
    ]
    return state
