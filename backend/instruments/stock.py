import yfinance as yf
from .base import InstrumentHandler


class StockHandler(InstrumentHandler):
    def asset_class(self) -> str:
        return "equity"

    async def fetch_current_value(self, metadata: dict) -> int | None:
        symbol = metadata.get("symbol")
        quantity = metadata.get("quantity")
        if not symbol or not quantity:
            return None
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            price = info.last_price
            if price is None:
                return None
            return int(price * float(quantity) * 100)
        except Exception:
            return None

    async def fetch_price(self, symbol: str) -> float | None:
        try:
            ticker = yf.Ticker(symbol)
            return ticker.fast_info.last_price
        except Exception:
            return None
