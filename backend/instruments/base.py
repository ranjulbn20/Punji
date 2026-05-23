from abc import ABC, abstractmethod


class InstrumentHandler(ABC):
    @abstractmethod
    async def fetch_current_value(self, metadata: dict) -> int | None:
        """Return current market value in INR paise (BigInteger), or None if unavailable."""

    @abstractmethod
    def asset_class(self) -> str:
        """Return the asset class string for this instrument type."""
