import csv
import io
from datetime import date
from .base import CSVImporter, HoldingDTO, TransactionDTO


def _f(s: str) -> float:
    return float(str(s).replace(",", "").strip() or "0")


class GrowwStocksImporter(CSVImporter):
    async def parse(self, content: bytes, filename: str, password: str = "") -> list[HoldingDTO]:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8", errors="replace")))
        holdings = []
        for row in reader:
            name = row.get("Stock Name", "").strip()
            if not name:
                continue
            qty = _f(row.get("Quantity", "0"))
            avg_price = _f(row.get("Average Price", "0"))
            cur_price = _f(row.get("Current Price", "0"))
            invested = round(_f(row.get("Invested Value", "0")), 2)
            current = round(qty * cur_price, 2)
            holdings.append(HoldingDTO(
                instrument_type="stock",
                display_name=name,
                asset_class="equity",
                invested_amount=invested,
                current_value=current,
                metadata={
                    "symbol": f"{name.replace(' ', '')}.NS",
                    "quantity": qty,
                    "average_price": avg_price,
                    "current_price": cur_price,
                },
                transactions=[
                    TransactionDTO(
                        transaction_date=date.today(),
                        transaction_type="buy",
                        amount=invested,
                        units=qty,
                        price=avg_price,
                    )
                ],
                confidence_score=0.9,
            ))
        return holdings


class GrowwMFImporter(CSVImporter):
    async def parse(self, content: bytes, filename: str, password: str = "") -> list[HoldingDTO]:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8", errors="replace")))
        holdings = []
        for row in reader:
            name = row.get("Fund Name", "").strip()
            if not name:
                continue
            units = _f(row.get("Units", "0"))
            avg_nav = _f(row.get("Average NAV", "0"))
            cur_nav = _f(row.get("Current NAV", "0"))
            invested = round(_f(row.get("Invested Amount", "0")), 2)
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
                confidence_score=0.9,
                warnings=["Scheme code not available in Groww CSV — XIRR accuracy may be reduced"],
            ))
        return holdings
