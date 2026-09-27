"""
News highlights — classifies news impact per stock holding and persists
highlights (critical/significant only, with the article link) for the
dashboard News section. Shares its classification logic with
agents/news_intelligence.py, which uses it in-memory for the chat pipeline.

Also home to classify_news_signal(), a separate structured (direction-aware,
positive or negative) classifier used only by services/signal_service.py's
proactive monitoring — kept distinct from classify_holding_news() so the
already-working dashboard/chat path is untouched by the newer signal engine.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from models import NewsHighlight
from services.instrument_service import get_instruments_by_type
from services.market_service import get_company_name, get_stock_price
from services.news_providers.fallback import FallbackNewsProvider
from services.news_providers.google_news_rss import GoogleNewsRSSProvider
from services.news_providers.yfinance_provider import YFinanceNewsProvider
from llm import NEWS_INTELLIGENCE

HIGHLIGHT_CATEGORIES = ("critical", "significant")
TOP_MOVERS_COUNT = 5

# Google News RSS primary (best Indian small/midcap coverage), yfinance as fallback
# in case the unofficial RSS endpoint changes format or starts rate-limiting.
NEWS_PROVIDER = FallbackNewsProvider(GoogleNewsRSSProvider(), YFinanceNewsProvider())


async def select_top_movers(db: AsyncSession, user_id, top_n: int = TOP_MOVERS_COUNT) -> list:
    """
    Return the user's stock holdings most worth spending a news-classification
    LLM call on: ranked by absolute day change (via the cheap, cached
    get_stock_price), largest movers first. Stocks whose price couldn't be
    fetched today are ranked last rather than excluded, so they still fill
    remaining slots if fewer than top_n stocks have real change data.
    """
    stocks = await get_instruments_by_type(db, user_id, "stock")
    stocks = [s for s in stocks if s.symbol]

    async def day_change(holding):
        price_data = await get_stock_price(holding.symbol)
        change_pct = price_data.get("change_pct") if price_data else None
        return abs(change_pct) if change_pct is not None else -1.0

    changes = [await day_change(h) for h in stocks]
    ranked = [h for _, h in sorted(zip(changes, stocks), key=lambda pair: pair[0], reverse=True)]
    return ranked[:top_n]


async def classify_holding_news(holding, symbol: str) -> list[dict]:
    """
    Fetch and classify recent news for one stock holding.
    Returns at most one highlight dict (only if category is critical/significant).
    """
    company_name = await get_company_name(symbol)
    news_items = await NEWS_PROVIDER.get_news(symbol, company_name)
    if not news_items:
        return []

    top_items = news_items[:5]
    numbered = "\n".join(f"{i + 1}. {n['title']}" for i, n in enumerate(top_items))

    prompt = f"""Classify the investment impact of these news headlines for {holding.display_name} (NSE: {symbol}).

Headlines:
{numbered}

Categories:
- critical: SEBI enforcement, promoter pledging, auditor resignation, sudden CEO exit, debt default
- significant: Major contract loss, earnings miss >20%, management change, credit rating downgrade
- monitor: Earnings miss <10%, minor regulatory notice, analyst downgrade
- noise: Routine results, general market news, analyst target adjustments

Return ONLY a JSON object: {{"category": "...", "headline_number": <the number 1-{len(top_items)} of the most important headline above>, "reason": "one sentence"}}"""

    try:
        classification = await NEWS_INTELLIGENCE.generate_json(prompt)
    except Exception:
        return []

    category = classification.get("category")
    if category not in HIGHLIGHT_CATEGORIES:
        return []

    idx = classification.get("headline_number")
    if not isinstance(idx, int) or not (1 <= idx <= len(top_items)):
        idx = 1
    chosen = top_items[idx - 1]

    return [{
        "instrument_type": "stock",
        "instrument_id": holding.id,
        "holding_name": holding.display_name,
        "symbol": symbol,
        "category": category,
        "headline": chosen["title"],
        "link": chosen["link"],
        "reason": classification.get("reason", ""),
    }]


async def classify_news_signal(holding, symbol: str) -> dict | None:
    """
    Structured, direction-aware event classification for the proactive signal
    engine (services/signal_service.py) — distinct from classify_holding_news
    (which only flags downside categories for the dashboard's News card).
    Returns None if no recent news, or nothing found material enough to
    matter (low materiality or a neutral read).
    """
    company_name = await get_company_name(symbol)
    news_items = await NEWS_PROVIDER.get_news(symbol, company_name)
    if not news_items:
        return None

    top_items = news_items[:5]
    numbered = "\n".join(f"{i + 1}. {n['title']}" for i, n in enumerate(top_items))

    prompt = f"""Analyse these recent news headlines for {holding.display_name} (NSE: {symbol}) and identify the single most impactful one.

Headlines:
{numbered}

Return ONLY a JSON object:
{{
  "headline_number": <1-{len(top_items)}, the number of the most impactful headline above>,
  "event_type": "regulatory|earnings|contract|management_change|credit_rating|guidance|corporate_action|other",
  "direction": "positive|negative|neutral",
  "materiality": "low|medium|high",
  "confidence": <0.0-1.0, how confident you are this is genuinely material and not routine noise>,
  "reason": "one sentence explaining the likely market impact"
}}"""

    try:
        result = await NEWS_INTELLIGENCE.generate_json(prompt)
    except Exception:
        return None

    if result.get("materiality") not in ("medium", "high") or result.get("direction") == "neutral":
        return None

    idx = result.get("headline_number")
    if not isinstance(idx, int) or not (1 <= idx <= len(top_items)):
        idx = 1
    chosen = top_items[idx - 1]

    try:
        confidence = float(result.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5

    return {
        "signal_type": "news",
        "direction": result.get("direction"),
        "severity": "high" if result.get("materiality") == "high" else "medium",
        "confidence": confidence,
        "evidence": [f"{result.get('event_type', 'news')}: {chosen['title']}"],
        "headline": chosen["title"],
        "link": chosen["link"],
        "reason": result.get("reason", ""),
    }


async def refresh_news_highlights(db: AsyncSession, user_id) -> list[NewsHighlight]:
    """Re-fetch and re-classify news for the user's top day-movers, replacing prior highlights."""
    top_holdings = await select_top_movers(db, user_id)

    highlights = []
    for holding in top_holdings:
        highlights.extend(await classify_holding_news(holding, holding.symbol))

    await db.execute(delete(NewsHighlight).where(NewsHighlight.user_id == user_id))
    rows = [NewsHighlight(user_id=user_id, **h) for h in highlights]
    db.add_all(rows)
    await db.commit()
    for row in rows:
        await db.refresh(row)
    return rows


async def get_news_highlights(db: AsyncSession, user_id) -> list[NewsHighlight]:
    result = await db.execute(
        select(NewsHighlight).where(NewsHighlight.user_id == user_id).order_by(NewsHighlight.created_at.desc())
    )
    return list(result.scalars().all())
