"""Wraps the existing yfinance-based news fetch as a BaseNewsProvider — used only as a fallback."""
from services.market_service import get_stock_news
from services.news_providers.base import BaseNewsProvider


class YFinanceNewsProvider(BaseNewsProvider):
    async def get_news(self, symbol: str, company_name: str) -> list[dict]:
        return await get_stock_news(symbol)
