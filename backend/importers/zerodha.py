import csv
import io
from datetime import date
from .base import CSVImporter, HoldingDTO, TransactionDTO


def _parse_float(s: str) -> float:
    return float(str(s).replace(",", "").strip() or "0")


class ZerodhaHoldingsImporter(CSVImporter):
    async def parse(self, content: bytes, filename: str, password: str = "") -> list[HoldingDTO]:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8", errors="replace")))
        holdings = []
        for row in reader:
            symbol = (row.get("Symbol") or row.get("Instrument") or "").strip()
            if not symbol:
                continue
            qty = _parse_float(row.get("Qty.", "0"))
            avg_cost = _parse_float(row.get("Avg. cost", "0"))
            ltp = _parse_float(row.get("LTP", "0"))
            invested = round(qty * avg_cost, 2)
            current = round(qty * ltp, 2)

            holdings.append(HoldingDTO(
                instrument_type="stock",
                display_name=symbol,
                asset_class="equity",
                invested_amount=invested,
                current_value=current,
                metadata={
                    "symbol": f"{symbol}.NS",
                    "isin": row.get("ISIN", "").strip(),
                    "exchange": "NSE",
                    "quantity": qty,
                    "average_price": avg_cost,
                    "current_price": ltp,
                },
                transactions=[
                    TransactionDTO(
                        transaction_date=date.today(),
                        transaction_type="buy",
                        amount=invested,
                        units=qty,
                        price=avg_cost,
                        notes="Imported from Zerodha holdings CSV",
                    )
                ],
                confidence_score=0.95,
            ))
        return holdings


class ZerodhaTradebookImporter(CSVImporter):
    async def parse(self, content: bytes, filename: str, password: str = "") -> list[HoldingDTO]:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8", errors="replace")))
        by_symbol: dict[str, list] = {}
        for row in reader:
            # Support both legacy uppercase and actual lowercase Zerodha tradebook headers
            symbol = (row.get("symbol") or row.get("Symbol") or "").strip()
            if not symbol:
                continue
            by_symbol.setdefault(symbol, []).append(row)

        holdings = []
        for symbol, rows in by_symbol.items():
            transactions = []
            total_qty = 0.0
            total_cost = 0.0
            for row in rows:
                trade_type = (row.get("trade_type") or row.get("Trade Type") or "").upper()
                qty = _parse_float(row.get("quantity") or row.get("Quantity") or "0")
                price = _parse_float(row.get("price") or row.get("Price") or "0")
                trade_id = (row.get("trade_id") or row.get("Trade ID") or "").strip()
                raw_date = (row.get("trade_date") or row.get("Trade Date") or "").strip()
                try:
                    tx_date = date.fromisoformat(raw_date[:10])
                except ValueError:
                    tx_date = date.today()
                amount = round(qty * price, 2)
                tx_type = "buy" if trade_type == "BUY" else "sell"
                # Embed trade_id in notes so the dedup query can distinguish
                # multiple trades with identical date/type/qty/price on the same day
                notes = f"trade_id:{trade_id}" if trade_id else None
                transactions.append(TransactionDTO(
                    transaction_date=tx_date,
                    transaction_type=tx_type,
                    amount=amount if tx_type == "buy" else -amount,
                    units=qty,
                    price=price,
                    notes=notes,
                ))
                if tx_type == "buy":
                    total_qty += qty
                    total_cost += amount
                else:
                    total_qty -= qty

            holdings.append(HoldingDTO(
                instrument_type="stock",
                display_name=symbol,
                asset_class="equity",
                invested_amount=round(total_cost, 2),
                current_value=round(total_cost, 2),  # no current price in tradebook
                metadata={"symbol": f"{symbol}.NS", "quantity": max(total_qty, 0)},
                transactions=transactions,
                confidence_score=0.85,
                warnings=["Current price not available in tradebook — will be refreshed"],
            ))
        return [h for h in holdings if h.transactions]
