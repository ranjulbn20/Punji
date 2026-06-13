"""
MF portfolio composition fetching and storage.

Design: CompositionProvider ABC + registry pattern so new data sources
can be added without touching the refresh orchestrator or the exposure service.

Default provider: LLMCompositionProvider — uses the project's LLM layer
(MARKET_INTELLIGENCE role) to retrieve portfolio composition from the model's
training data. AMFI publishes monthly disclosures; LLMs trained on this data
can accurately recall top holdings for most Indian equity funds.
"""
from __future__ import annotations

import asyncio
import json
import re
import yfinance as yf
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class CompositionEntry:
    company_isin: str
    company_name: str
    weight_pct: float
    sector: str | None = None


class CompositionProvider(ABC):
    @abstractmethod
    async def fetch(self, scheme_code: int, scheme_name: str = "") -> list[CompositionEntry]:
        """Return the latest known portfolio composition for a scheme."""
        ...


# ── LLM provider (default) ────────────────────────────────────────────────────

class LLMCompositionProvider(CompositionProvider):
    """
    Uses the project's MARKET_INTELLIGENCE LLM role to retrieve mutual fund
    portfolio composition from the model's training data.

    AMFI mandates monthly portfolio disclosures for all Indian mutual funds.
    This data is widely available in financial news and fund house websites,
    and is well-represented in LLM training corpora up to the knowledge cutoff.

    Limitations:
    - Data reflects the model's knowledge cutoff (~mid-2025), not today's date.
    - May be less accurate for very small or recently launched funds.
    - ISINs may occasionally be incorrect; company_name is used as display label.
    """

    _PROMPT_TEMPLATE = """\
You are a financial data assistant specialising in Indian mutual funds.

Retrieve the latest known portfolio holdings for this fund:
  Fund name : {scheme_name}
  AMFI code  : {scheme_code}

Return ONLY a JSON object in this exact shape — no explanation, no markdown:
{{
  "holdings": [
    {{
      "company_name": "Full company name",
      "company_isin": "12-char NSE ISIN starting with IN, or empty string if unknown",
      "weight_pct": 5.2,
      "sector": "Sector label e.g. Financial Services, IT, FMCG, Auto, Pharma, Energy, Metals, Telecom, Healthcare, Consumer Durables, Real Estate, Chemicals, Cement"
    }}
  ]
}}

Rules:
- Include the top 25 equity holdings only (skip cash, debt instruments, REITs unless the fund is debt/hybrid).
- weight_pct is the percentage of NAV allocated to that company (e.g. 5.2 means 5.2%).
- All weights must be positive numbers.
- Sector must be a concise label matching Indian market conventions.
- ISIN UNIQUENESS IS CRITICAL: every company has exactly one ISIN. No two entries in your list may share the same company_isin. If you are not 100% certain which ISIN belongs to a company, use empty string — never assign one company's ISIN to a different company.
- If you are not confident about an ISIN, return an empty string. Wrong ISINs corrupt the portfolio look-through. An empty string is always safer than a guess.
- Double-check: HDFC Bank = INE040A01034, Reliance = INE002A01018, Infosys = INE009A01021, TCS = INE467B01029, ICICI Bank = INE090A01021. If a company's ISIN does not match your confident recall, use empty string.
"""

    def _get_provider(self):
        from llm.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(model="gpt-4o-mini", temperature=0.1)

    async def fetch(self, scheme_code: int, scheme_name: str = "") -> list[CompositionEntry]:
        if not scheme_name:
            scheme_name = f"scheme code {scheme_code}"

        prompt = self._PROMPT_TEMPLATE.format(
            scheme_name=scheme_name,
            scheme_code=scheme_code,
        )

        try:
            raw = await self._get_provider().generate_json(prompt)
        except Exception as e:
            print(f"[LLMComposition] LLM call failed for {scheme_code}: {e}")
            return []

        holdings = raw.get("holdings", [])
        if not isinstance(holdings, list):
            print(f"[LLMComposition] Unexpected response shape for {scheme_code}: {type(holdings)}")
            return []

        entries: list[CompositionEntry] = []
        for h in holdings:
            try:
                weight = float(h.get("weight_pct", 0) or 0)
                if weight <= 0:
                    continue
                isin = (h.get("company_isin") or "").strip()
                # Validate ISIN format; clear if it looks wrong
                if isin and (len(isin) != 12 or not isin.startswith("IN")):
                    isin = ""
                entries.append(CompositionEntry(
                    company_isin=isin,
                    company_name=(h.get("company_name") or "").strip(),
                    weight_pct=round(weight, 3),
                    sector=(h.get("sector") or "").strip() or None,
                ))
            except (TypeError, ValueError):
                continue

        return entries


# ── AMFI file provider (fallback / future) ────────────────────────────────────

class AMFICompositionProvider(CompositionProvider):
    """
    Fetches portfolio composition from AMFI's monthly portfolio disclosure files.
    AMFI does not currently expose a stable public JSON API; this provider
    tries known URL patterns and returns an empty list if all fail.
    """

    _CANDIDATE_URL_PATTERNS = [
        "https://portal.amfiindia.com/PortalBackEnd/MFDocuments/PortfolioDetails_{month_year}.txt",
        "https://www.amfiindia.com/Themes/Theme1/downloads/PortfolioDetails_{month_year}.txt",
    ]
    _TIMEOUT = 30

    def _prev_month_year(self) -> str:
        """Return the most recently published portfolio disclosure month (previous month)."""
        today = date.today()
        first = today.replace(day=1)
        prev_last = first - timedelta(days=1)
        return prev_last.strftime("%B%Y")   # e.g. "May2026"

    async def _download_portfolio_file(self, month_year: str) -> str | None:
        import httpx
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        async with httpx.AsyncClient(timeout=self._TIMEOUT, follow_redirects=True, headers=headers) as c:
            for pattern in self._CANDIDATE_URL_PATTERNS:
                url = pattern.format(month_year=month_year)
                try:
                    resp = await c.get(url)
                    if resp.status_code == 200 and len(resp.text) > 1000:
                        return resp.text
                except Exception:
                    continue
        return None

    def _parse(self, text: str, scheme_code: int) -> list[CompositionEntry]:
        entries: list[CompositionEntry] = []
        in_target = False
        for line in text.splitlines():
            line = line.strip()
            if not line:
                if in_target and entries:
                    break
                continue
            parts = [p.strip() for p in line.split(";")]
            if len(parts) < 3:
                if str(scheme_code) in line:
                    in_target = True
                elif in_target:
                    in_target = False
                continue
            if not in_target:
                continue
            try:
                isin = parts[1] if len(parts) > 1 else ""
                if not isin or len(isin) < 8 or not isin.startswith("IN"):
                    continue
                weight = float((parts[4] if len(parts) > 4 else parts[-1]).replace(",", ""))
                if weight <= 0:
                    continue
                entries.append(CompositionEntry(
                    company_isin=isin,
                    company_name=parts[0],
                    weight_pct=round(weight, 3),
                ))
            except (ValueError, IndexError):
                continue
        return entries

    async def fetch(self, scheme_code: int, scheme_name: str = "") -> list[CompositionEntry]:
        text = await self._download_portfolio_file(self._prev_month_year())
        if not text:
            return []
        return self._parse(text, scheme_code)


# ── Sector enrichment ─────────────────────────────────────────────────────────

async def _enrich_sectors(entries: list[CompositionEntry]) -> None:
    """Fill missing sector info via yfinance for entries that have a valid ISIN."""
    sem = asyncio.Semaphore(5)

    async def _fetch_one(entry: CompositionEntry) -> None:
        async with sem:
            try:
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(
                    None,
                    lambda: yf.Ticker(entry.company_isin + ".NS").info,
                )
                sector = info.get("sector") or info.get("industryDisp")
                if sector:
                    entry.sector = sector
            except Exception:
                pass

    need_sector = [e for e in entries if e.sector is None and e.company_isin]
    if need_sector:
        await asyncio.gather(*[_fetch_one(e) for e in need_sector])


# ── Orchestration ─────────────────────────────────────────────────────────────

async def refresh_composition(
    db: AsyncSession,
    scheme_code: int,
    disclosure_month: date,
    provider: CompositionProvider,
    scheme_name: str = "",
) -> int:
    """
    Fetch composition for one scheme and upsert into fund_compositions.
    Returns the number of rows upserted.
    """
    from models import FundComposition

    entries = await provider.fetch(scheme_code, scheme_name=scheme_name)
    if not entries:
        return 0

    await _enrich_sectors(entries)

    month_first = disclosure_month.replace(day=1)

    # Deduplicate by ISIN: LLMs occasionally assign the same ISIN to two companies.
    # PostgreSQL's ON CONFLICT DO UPDATE cannot resolve duplicates within a single
    # INSERT batch, so we must resolve them here. Keep the highest weight entry.
    # Skip entries with no ISIN — they can't be matched for look-through anyway.
    seen_isin: dict[str, CompositionEntry] = {}
    for e in entries:
        if not e.company_name or not e.company_isin:
            continue
        existing = seen_isin.get(e.company_isin)
        if existing is None or e.weight_pct > existing.weight_pct:
            seen_isin[e.company_isin] = e

    rows = [
        {
            "scheme_code": scheme_code,
            "company_isin": e.company_isin,
            "company_name": e.company_name,
            "sector": e.sector,
            "weight_pct": e.weight_pct,
            "disclosure_month": month_first,
        }
        for e in seen_isin.values()
    ]
    if not rows:
        return 0

    stmt = pg_insert(FundComposition).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_fund_comp",
        set_={
            "company_name": stmt.excluded.company_name,
            "sector": stmt.excluded.sector,
            "weight_pct": stmt.excluded.weight_pct,
        },
    )
    await db.execute(stmt)
    await db.commit()
    return len(rows)


async def get_or_refresh_all(
    db: AsyncSession,
    scheme_codes: set[int],
    provider: CompositionProvider | None = None,
) -> dict[int, int]:
    """
    Refresh composition for all supplied scheme codes using the given provider
    (defaults to LLMCompositionProvider).
    Returns {scheme_code: rows_upserted}.
    """
    if provider is None:
        provider = LLMCompositionProvider()

    from models import FundComposition, MutualFund

    today_first = date.today().replace(day=1)

    # Skip schemes already refreshed this month
    existing_result = await db.execute(
        select(FundComposition.scheme_code)
        .where(FundComposition.disclosure_month == today_first)
        .distinct()
    )
    already_fresh = {row[0] for row in existing_result}
    stale = scheme_codes - already_fresh

    if not stale:
        return {}

    # Load scheme names for better LLM prompts
    name_result = await db.execute(
        select(MutualFund.scheme_code, MutualFund.display_name)
        .where(MutualFund.scheme_code.in_(stale), MutualFund.is_active == True)
        .distinct(MutualFund.scheme_code)
    )
    scheme_names: dict[int, str] = {row[0]: row[1] for row in name_result}

    results: dict[int, int] = {}
    for sc in stale:
        name = scheme_names.get(sc, "")
        try:
            count = await refresh_composition(db, sc, today_first, provider, scheme_name=name)
            results[sc] = count
            print(f"[Composition] scheme {sc} ({name}): {count} rows upserted")
        except Exception as e:
            print(f"[Composition] scheme {sc} ({name}): error — {e}")
            results[sc] = 0

    return results
