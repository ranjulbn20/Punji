import re
import io
import csv
from datetime import date, datetime
from .base import CSVImporter, HoldingDTO, TransactionDTO


def _parse_signed_amount(s: str) -> float:
    """Parse amounts like '24,998.75' or '(26,193.75)' (negative in parens)."""
    s = s.strip()
    negative = s.startswith("(") and s.endswith(")")
    val = float(re.sub(r"[(),\s,]", "", s).replace(",", "") or "0")
    return -val if negative else val


def _guess_asset_class(scheme_name: str) -> str:
    # Strip "(formerly ...)" clauses before classifying to avoid false positives from old names
    primary = re.sub(r"\(formerly[^)]*\)", "", scheme_name, flags=re.IGNORECASE).lower()
    lower = primary
    if any(w in lower for w in [
        "liquid", "overnight", "money market", "ultra short", "low duration", "savings fund"
    ]):
        return "cash"
    if any(w in lower for w in [
        "debt", "bond", "gilt", "income", "credit risk", "banking and psu",
        "corporate bond", "short duration", "medium duration", "long duration",
        "dynamic bond", "fixed maturity", "floating rate", "arbitrage",
    ]):
        return "debt"
    if any(w in lower for w in ["gold", "silver", "commodity"]):
        return "gold"
    return "equity"  # equity, hybrid, multi-asset, international all default here


class CAMSCASImporter(CSVImporter):
    """
    Parses CAMS/KFintech Consolidated Account Statement PDF or CSV.
    PDF password is typically the investor's PAN number in uppercase.
    """

    async def parse(self, content: bytes, filename: str, password: str = "") -> list[HoldingDTO]:
        if filename.lower().endswith(".pdf"):
            return await self._parse_pdf(content, password=password)
        return await self._parse_csv(content)

    async def _parse_pdf(self, content: bytes, password: str = "") -> list[HoldingDTO]:
        try:
            import pdfplumber
        except ImportError:
            return []

        open_kwargs = {"password": password} if password else {}
        with pdfplumber.open(io.BytesIO(content), **open_kwargs) as pdf:
            full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        return self._extract_from_text(full_text)

    async def _parse_csv(self, content: bytes) -> list[HoldingDTO]:
        return self._extract_from_text(content.decode("utf-8", errors="replace"))

    def _extract_from_text(self, text: str) -> list[HoldingDTO]:
        """
        CAMS CAS PDF text structure per fund block:

          Folio No: XXXXXXXXXX / 0  [KYC/PAN info]
          Holder Name
          SCHEME_CODE-Scheme Full Name - ISIN: XXXXXX  Registrar : CAMS/KFINTECH
          Nominee 1: ...
          Opening Unit Balance: X.XXX
          DD-Mon-YYYY  Description  Amount  Units  NAV  UnitBalance
          DD-Mon-YYYY  *** Stamp Duty ***  amount
          ...
          Closing Unit Balance: X.XXX NAV on DD-Mon-YYYY: INR X.XX
                 Total Cost Value: X.XX  Market Value on DD-Mon-YYYY: INR X.XX
        """
        holdings: list[HoldingDTO] = []
        lines = [ln.strip() for ln in text.split("\n")]

        # State
        current_scheme: str | None = None
        current_folio: str | None = None
        transactions: list[TransactionDTO] = []

        # Patterns
        folio_re = re.compile(r"Folio\s+No\s*:\s*(\S+)", re.IGNORECASE)

        # Scheme line starts with an alphanumeric code, dash, scheme name, then " - ISIN:"
        isin_line_re = re.compile(r"^[A-Z0-9]+-(.+?)\s+-\s+ISIN:", re.IGNORECASE)

        # Closing balance line — all on one line in the PDF
        closing_re = re.compile(
            r"Closing\s+Unit\s+Balance\s*:\s*([\d,\.]+).*?"
            r"Total\s+Cost\s+Value\s*:\s*([\d,\.]+).*?"
            r"Market\s+Value.*?INR\s*([\d,\.]+)",
            re.IGNORECASE,
        )

        # Transaction line: date + description + Amount + Units + NAV + UnitBalance (4 numbers)
        # Amount and Units can be negative (parenthesised). NAV and UnitBalance are always positive.
        tx_re = re.compile(
            r"^(\d{2}-[A-Za-z]{3}-\d{4})\s+"   # date
            r"(.+?)\s+"                           # description (non-greedy)
            r"(\(?[\d,]+\.[\d]+\)?)\s+"           # Amount
            r"(\(?[\d,]+\.[\d]+\)?)\s+"           # Units
            r"([\d,]+\.[\d]+)\s+"                 # NAV / Price
            r"([\d,]+\.[\d]+)\s*$",               # Unit Balance
        )

        for line in lines:
            if not line:
                continue

            # Skip stamp duty, admin notices, page headers
            if "***" in line:
                continue
            if line.startswith("Date Transaction") or line.startswith("(INR)"):
                continue

            # ── Folio number (marks start of a new fund block) ──────────────
            folio_match = folio_re.search(line)
            if folio_match:
                current_folio = folio_match.group(1).strip().rstrip("/").strip()
                # Reset scheme — it will be set by the ISIN line that follows
                current_scheme = None
                transactions = []
                continue

            # ── Scheme name (from ISIN line) ─────────────────────────────────
            isin_match = isin_line_re.match(line)
            if isin_match:
                current_scheme = isin_match.group(1).strip()
                transactions = []
                continue

            # ── Closing balance — emit the holding ───────────────────────────
            closing_match = closing_re.search(line)
            if closing_match and current_scheme:
                units = float(closing_match.group(1).replace(",", ""))
                cost_value = float(closing_match.group(2).replace(",", ""))
                market_value = float(closing_match.group(3).replace(",", ""))

                holdings.append(HoldingDTO(
                    instrument_type="mutual_fund",
                    display_name=current_scheme,
                    asset_class=_guess_asset_class(current_scheme),
                    invested_amount=round(cost_value, 2),
                    current_value=round(market_value, 2),
                    metadata={
                        "units": units,
                        "folio_number": current_folio or "",
                    },
                    transactions=transactions[:],
                    confidence_score=0.97,
                ))
                current_scheme = None
                current_folio = None
                transactions = []
                continue

            # ── Transaction line ─────────────────────────────────────────────
            tx_match = tx_re.match(line)
            if tx_match and current_scheme:
                try:
                    tx_date = datetime.strptime(tx_match.group(1), "%d-%b-%Y").date()
                    desc = tx_match.group(2).strip()
                    amount = _parse_signed_amount(tx_match.group(3))
                    units = _parse_signed_amount(tx_match.group(4))
                    nav = float(tx_match.group(5).replace(",", ""))

                    desc_lower = desc.lower()
                    if any(w in desc_lower for w in ["redemption", "switch out", "switched-out", "withdrawal"]):
                        tx_type = "sell"
                    elif any(w in desc_lower for w in ["sip", "systematic investment"]):
                        tx_type = "sip"
                    elif "dividend" in desc_lower:
                        tx_type = "dividend_reinvest"
                    else:
                        tx_type = "buy"  # purchase, nfo purchase, switch in, etc.

                    transactions.append(TransactionDTO(
                        transaction_date=tx_date,
                        transaction_type=tx_type,
                        amount=round(abs(amount), 2) if tx_type != "sell" else -round(abs(amount), 2),
                        units=abs(units),
                        price=nav,
                        notes=desc[:120],
                    ))
                except (ValueError, IndexError):
                    pass

        return holdings
