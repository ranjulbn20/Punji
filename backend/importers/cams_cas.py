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
          ...
          [Line A] Closing Unit Balance: X.XXX  NAV on DD-Mon-YYYY: INR X.XX  Market Value on DD-Mon-YYYY: INR X.XX
          [exit load text]
          [Line B] Closing Unit Balance: X.XXX  Total Cost Value: X.XX
        """
        holdings: list[HoldingDTO] = []
        lines = [ln.strip() for ln in text.split("\n")]

        # State
        current_scheme: str | None = None
        current_isin: str | None = None
        current_folio: str | None = None
        transactions: list[TransactionDTO] = []

        # Patterns
        folio_re = re.compile(r"Folio\s+No\s*:\s*(\S+)", re.IGNORECASE)

        # Scheme line: code-SchemeNameParts - ISIN: CODE
        # Group 1 = scheme name, Group 2 = ISIN code
        isin_line_re = re.compile(
            r"^[A-Z0-9]+-(.+?)\s+-\s+ISIN:\s*([A-Z0-9]+)",
            re.IGNORECASE,
        )

        # pdfplumber joins the closing summary into one line:
        # "Closing Unit Balance: X  NAV on DD-Mon-YYYY: INR X  Total Cost Value: X  Market Value on ...: INR X"
        # Group 1 = closing units, Group 2 = current NAV, Group 3 = total cost, Group 4 = market value
        closing_re = re.compile(
            r"Closing\s+Unit\s+Balance\s*:\s*([\d,\.]+).*?"
            r"NAV\s+on.*?INR\s*([\d,\.]+).*?"
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

            # ── Folio number ──────────────────────────────────────────────────
            # In CAMS CAS PDFs the ISIN line always precedes the Folio No line,
            # so we must NOT reset current_scheme here.
            folio_match = folio_re.search(line)
            if folio_match:
                current_folio = folio_match.group(1).strip().rstrip("/").strip()
                continue

            # ── ISIN continuation (long scheme names wrap the ISIN to next line) ─
            # ISINs are always 12 chars; if we have a partial one, try to extend.
            if current_isin and len(current_isin) < 12:
                cont = re.match(r"^([A-Z0-9]+)", line, re.IGNORECASE)
                if cont:
                    current_isin = (current_isin + cont.group(1).upper())[:12]
                    continue

            # ── Scheme name + ISIN (from ISIN line) ──────────────────────────
            isin_match = isin_line_re.match(line)
            if isin_match:
                current_scheme = isin_match.group(1).strip()
                current_isin = isin_match.group(2).strip().upper()
                transactions = []
                continue

            # ── Closing summary line — emit the holding ──────────────────────
            closing_match = closing_re.search(line)
            if closing_match and current_scheme:
                units = float(closing_match.group(1).replace(",", ""))
                current_nav = float(closing_match.group(2).replace(",", ""))
                cost_value = float(closing_match.group(3).replace(",", ""))
                market_value = float(closing_match.group(4).replace(",", ""))
                avg_nav = round(cost_value / units, 4) if units else 0.0

                holdings.append(HoldingDTO(
                    instrument_type="mutual_fund",
                    display_name=current_scheme,
                    asset_class=_guess_asset_class(current_scheme),
                    invested_amount=round(cost_value, 2),
                    current_value=round(market_value, 2),
                    metadata={
                        "isin": current_isin or "",
                        "units": units,
                        "current_nav": current_nav,
                        "average_nav": avg_nav,
                        "folio_number": current_folio or "",
                    },
                    transactions=transactions[:],
                    confidence_score=0.97,
                ))
                current_scheme = None
                current_isin = None
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
