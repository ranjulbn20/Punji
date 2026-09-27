"""
Abstract interface for stock news sources.
Every provider returns the same shape: title, publisher, link, published_at.
Callers never branch on which provider is active — see fallback.py.
"""
from abc import ABC, abstractmethod


class BaseNewsProvider(ABC):
    @abstractmethod
    async def get_news(self, symbol: str, company_name: str) -> list[dict]:
        """
        Recent news for one stock. `symbol` is the exchange ticker (e.g.
        "GILLETTE.NS"), `company_name` is the fuller resolved name used for
        providers where the bare ticker is too ambiguous to search with.
        Returns [] on no results or any provider-side failure — never raises.
        """
        ...
