import csv
import io
from datetime import date
from .base import CSVImporter, HoldingDTO, TransactionDTO


def _f(s: str) -> float:
    return float(str(s).replace(",", "").strip() or "0")


class KuveraImporter(CSVImporter):
    async def parse(self, content: bytes, filename: str, password: str = "") -> list[HoldingDTO]:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8", errors="replace")))
        holdings = []
        for row in reader:
            name = row.get("Scheme Name", "").strip()
            if not name:
                continue
            units = _f(row.get("Units", "0"))
            avg_nav = _f(row.get("Average NAV", "0"))
            cur_nav = _f(row.get("Current NAV", "0"))
            folio = row.get("Folio", "").strip()
            invested = round(units * avg_nav, 2)
            current = round(units * cur_nav, 2)
            holdings.append(HoldingDTO(
                instrument_type="mutual_fund",
                display_name=name,
                asset_class="equity",
                invested_amount=invested,
                current_value=current,
                metadata={
                    "units": units,
                    "average_nav": avg_nav,
                    "current_nav": cur_nav,
                    "folio_number": folio,
                },
                transactions=[
                    TransactionDTO(
                        transaction_date=date.today(),
                        transaction_type="buy",
                        amount=invested,
                        units=units,
                        price=avg_nav,
                    )
                ],
                confidence_score=0.92,
            ))
        return holdings
