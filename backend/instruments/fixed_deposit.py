from datetime import date
from .base import InstrumentHandler


class FixedDepositHandler(InstrumentHandler):
    def asset_class(self) -> str:
        return "debt"

    async def fetch_current_value(self, metadata: dict) -> int | None:
        """Compute accrued FD value based on compound interest formula."""
        try:
            principal = float(metadata.get("principal_amount", 0))
            rate = float(metadata.get("interest_rate", 0)) / 100
            start = date.fromisoformat(metadata.get("start_date"))
            compounding = metadata.get("compounding_frequency", "quarterly")
            freq_map = {"monthly": 12, "quarterly": 4, "half_yearly": 2, "annually": 1}
            n = freq_map.get(compounding, 4)
            days_elapsed = (date.today() - start).days
            years = days_elapsed / 365
            value = principal * ((1 + rate / n) ** (n * years))
            return int(value * 100)
        except Exception:
            return None
