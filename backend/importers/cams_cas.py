import re
import io
import csv
from datetime import date, datetime
from .base import CSVImporter, HoldingDTO, TransactionDTO


def _parse_amount(s: str) -> float:
    return float(re.sub(r"[^\d.]", "", s or "0") or "0")


class CAMSCASImporter(CSVImporter):
    """
    Parses CAMS Consolidated Account Statement (PDF text or CSV).
    CAMS CAS covers all mutual fund holdings across all platforms.
    """

    async def parse(self, content: bytes, filename: str) -> list[HoldingDTO]:
        if filename.lower().endswith(".pdf"):
            return await self._parse_pdf(content)
        return await self._parse_csv(content)

    async def _parse_pdf(self, content: bytes) -> list[HoldingDTO]:
        try:
            import pdfplumber
        except ImportError:
            return []

        holdings = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        holdings = self._extract_from_text(full_text)
        return holdings

    async def _parse_csv(self, content: bytes) -> list[HoldingDTO]:
        text = content.decode("utf-8", errors="replace")
        return self._extract_from_text(text)

    def _extract_from_text(self, text: str) -> list[HoldingDTO]:
        """
        CAMS CAS text format — each fund appears as a block:
          Fund Name
          Folio: XXXXXXX
          Date       Transaction           Units    Price    Amount
          ...
          Closing Balance: X.XXX units at NAV X.XX = X,XX,XXX.XX
        """
        holdings = []
        current_fund: str | None = None
        current_folio: str | None = None
        transactions: list[TransactionDTO] = []
        closing_balance: dict = {}

        lines = text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Fund name detection (usually all caps or title case before Folio line)
            if re.match(r"Folio\s*No\s*[:\-]\s*(.+)", line, re.IGNORECASE):
                current_folio = re.match(r"Folio\s*No\s*[:\-]\s*(.+)", line, re.IGNORECASE).group(1).strip()

            elif re.match(r"^Folio\s*:\s*(.+)", line, re.IGNORECASE):
                current_folio = line.split(":", 1)[1].strip()
                if i > 0:
                    current_fund = lines[i - 1].strip()

            # Closing balance detection
            closing_match = re.search(
                r"Closing\s+Balance\s*:?\s*([\d,\.]+)\s+[Uu]nit.*?NAV\s+([\d,\.]+).*?=\s*([\d,\.]+)",
                line
            )
            if closing_match and current_fund:
                units = float(closing_match.group(1).replace(",", ""))
                nav = float(closing_match.group(2).replace(",", ""))
                value = float(closing_match.group(3).replace(",", ""))
                closing_balance = {"units": units, "nav": nav, "value": value}

                holdings.append(HoldingDTO(
                    instrument_type="mutual_fund",
                    display_name=current_fund,
                    asset_class="equity",
                    invested_amount=int(sum(
                        t.amount for t in transactions if t.transaction_type in ("buy", "sip")
                    )),
                    current_value=int(value * 100),
                    metadata={
                        "units": units,
                        "current_nav": nav,
                        "folio_number": current_folio or "",
                    },
                    transactions=transactions[:],
                    confidence_score=0.97,
                ))
                transactions = []
                current_fund = None
                current_folio = None

            # Transaction line detection
            tx_match = re.match(
                r"(\d{2}-[A-Za-z]{3}-\d{4})\s+(.+?)\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)",
                line
            )
            if tx_match:
                try:
                    tx_date = datetime.strptime(tx_match.group(1), "%d-%b-%Y").date()
                    desc = tx_match.group(2).strip()
                    units = float(tx_match.group(3).replace(",", ""))
                    nav = float(tx_match.group(4).replace(",", ""))
                    amount = float(tx_match.group(5).replace(",", ""))

                    tx_type = "buy"
                    if any(word in desc.lower() for word in ["redemption", "withdrawal", "sell"]):
                        tx_type = "sell"
                    elif "sip" in desc.lower():
                        tx_type = "sip"
                    elif "dividend" in desc.lower():
                        tx_type = "dividend_reinvest"

                    transactions.append(TransactionDTO(
                        transaction_date=tx_date,
                        transaction_type=tx_type,
                        amount=int(amount * 100) if tx_type in ("buy", "sip") else -int(amount * 100),
                        units=units,
                        price=nav,
                        notes=desc,
                    ))
                except (ValueError, IndexError):
                    pass

            i += 1

        return holdings
