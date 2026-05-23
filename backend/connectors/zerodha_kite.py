"""Zerodha Kite connector — stub only, not functional in v1."""
from datetime import date
from .base import InstrumentConnector


class ZerodhaKiteConnector(InstrumentConnector):
    async def authenticate(self, auth_code: str) -> str:
        raise NotImplementedError("Zerodha Kite connector not available in v1")

    async def get_holdings(self, token: str) -> list[dict]:
        raise NotImplementedError("Zerodha Kite connector not available in v1")

    async def get_transactions(self, token: str, from_date: date) -> list[dict]:
        raise NotImplementedError("Zerodha Kite connector not available in v1")

    async def token_is_valid(self, token: str) -> bool:
        return False
