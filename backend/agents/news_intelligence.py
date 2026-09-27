"""News Intelligence Agent — classifies news impact for each holding."""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from agents.state import PunjiState
from services.instrument_service import get_instruments_by_type
from services.news_service import classify_holding_news


async def news_intelligence_node(state: PunjiState, db: AsyncSession | None = None) -> PunjiState:
    if not db:
        return state

    user_id = uuid.UUID(state["user_id"])

    stocks = await get_instruments_by_type(db, user_id, "stock")

    alerts = []
    for holding in stocks[:10]:  # limit to avoid rate limits
        symbol = holding.symbol
        if not symbol:
            continue
        alerts.extend(await classify_holding_news(holding, symbol))

    state["news_alerts"] = alerts
    state["reasoning_trace"] = state.get("reasoning_trace", []) + [
        f"NewsIntelligence: {len(alerts)} significant news items found across {len(stocks)} holdings"
    ]
    return state
