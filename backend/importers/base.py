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
class HoldingDTO:
    instrument_type: str
    display_name: str
    asset_class: str
    invested_amount: float
    current_value: float
    metadata: dict = field(default_factory=dict)
    transactions: list[TransactionDTO] = field(default_factory=list)
    confidence_score: float = 1.0
    warnings: list[str] = field(default_factory=list)


class CSVImporter(ABC):
    @abstractmethod
    async def parse(self, content: bytes, filename: str, password: str = "") -> list[HoldingDTO]:
        """Parse file content and return list of HoldingDTOs."""
