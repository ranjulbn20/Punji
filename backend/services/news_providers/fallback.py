"""
Fallback news provider — tries a primary source and falls through to a
secondary if the primary returns nothing (not just on exceptions: a provider
having no coverage for a stock is the expected, common case here, not an
error condition).
"""
from services.news_providers.base import BaseNewsProvider


class FallbackNewsProvider(BaseNewsProvider):
    def __init__(self, primary: BaseNewsProvider, fallback: BaseNewsProvider):
        self._primary = primary
        self._fallback = fallback

    async def get_news(self, symbol: str, company_name: str) -> list[dict]:
        items = await self._primary.get_news(symbol, company_name)
        if items:
            return items
        return await self._fallback.get_news(symbol, company_name)
