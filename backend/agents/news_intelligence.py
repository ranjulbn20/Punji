"""News Intelligence Agent — classifies news impact for each holding."""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from agents.state import PunjiState
from services.instrument_service import get_instruments_by_type
from services.market_service import get_stock_news
from llm import NEWS_INTELLIGENCE


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

        news_items = await get_stock_news(symbol)
        if not news_items:
            continue

        headlines = "\n".join(f"- {n['title']}" for n in news_items[:5])

        prompt = f"""Classify the investment impact of these news headlines for {holding.display_name} (NSE: {symbol}).

Headlines:
{headlines}

Categories:
- critical: SEBI enforcement, promoter pledging, auditor resignation, sudden CEO exit, debt default
- significant: Major contract loss, earnings miss >20%, management change, credit rating downgrade
- monitor: Earnings miss <10%, minor regulatory notice, analyst downgrade
- noise: Routine results, general market news, analyst target adjustments

Return ONLY a JSON object: {{"category": "...", "headline": "most important headline", "reason": "one sentence"}}"""

        try:
            classification = await NEWS_INTELLIGENCE.generate_json(prompt)

            if classification["category"] in ("critical", "significant"):
                alerts.append({
                    "instrument_type": "stock",
                    "instrument_id": str(holding.id),
                    "holding_name": holding.display_name,
                    "symbol": symbol,
                    "category": classification["category"],
                    "headline": classification.get("headline", ""),
                    "reason": classification.get("reason", ""),
                })
        except Exception:
            continue

    state["news_alerts"] = alerts
    state["reasoning_trace"] = state.get("reasoning_trace", []) + [
        f"NewsIntelligence: {len(alerts)} significant news items found across {len(holdings)} holdings"
    ]
    return state
