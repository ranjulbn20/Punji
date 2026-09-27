"""News Intelligence Agent — classifies news impact for each holding."""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from agents.state import PunjiState
from services.news_service import classify_holding_news, select_top_movers


async def news_intelligence_node(state: PunjiState, db: AsyncSession | None = None) -> PunjiState:
    if not db:
        return state

    user_id = uuid.UUID(state["user_id"])

    top_holdings = await select_top_movers(db, user_id)

    alerts = []
    for holding in top_holdings:
        alerts.extend(await classify_holding_news(holding, holding.symbol))

    state["news_alerts"] = alerts
    state["reasoning_trace"] = state.get("reasoning_trace", []) + [
        f"NewsIntelligence: {len(alerts)} significant news items found across {len(top_holdings)} top movers"
    ]
    return state
