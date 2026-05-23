from abc import ABC, abstractmethod
from datetime import date


class InstrumentConnector(ABC):
    """Abstract interface for live broker connections. Implemented in v2."""

    @abstractmethod
    async def authenticate(self, auth_code: str) -> str:
        """Exchange auth code for access token. Returns token."""

    @abstractmethod
    async def get_holdings(self, token: str) -> list[dict]:
        """Return list of holdings from broker."""

    @abstractmethod
    async def get_transactions(self, token: str, from_date: date) -> list[dict]:
        """Return list of transactions from broker."""

    @abstractmethod
    async def token_is_valid(self, token: str) -> bool:
        """Check if token is still valid."""
