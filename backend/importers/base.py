from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date


@dataclass
class TransactionDTO:
    transaction_date: date
    transaction_type: str
    amount: float
    units: float | None = None
    price: float | None = None
    notes: str | None = None


@dataclass
class StockTradeDTO:
    """Individual stock trade execution — used by tradebook importers."""
    trade_date: date
    trade_type: str        # "buy" | "sell"
    quantity: float
    price: float
    amount: float          # positive for buys, negative for sells
    exchange: str = "NSE"
    segment: str = "EQ"
    trade_id: str = ""     # broker's execution ID, used for dedup


@dataclass
class HoldingDTO:
    instrument_type: str
    display_name: str
    asset_class: str
    invested_amount: float
    current_value: float
    metadata: dict = field(default_factory=dict)
    transactions: list[TransactionDTO] = field(default_factory=list)   # MF / FD / PPF / NPS
    stock_trades: list[StockTradeDTO] = field(default_factory=list)    # stocks only (tradebook)
    confidence_score: float = 1.0
    warnings: list[str] = field(default_factory=list)


class CSVImporter(ABC):
    @abstractmethod
    async def parse(self, content: bytes, filename: str, password: str = "") -> list[HoldingDTO]:
        """Parse file content and return list of HoldingDTOs."""
