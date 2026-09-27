"""
Benchmark comparison — distinguishes a company-specific price move from a
broad market/sector one. Two independent levels:

  Market:   every stock compared against NIFTY 50.
  Industry: a small static mapping from yfinance's granular `industry` field
            (not the broad `sector` — e.g. "Financial Services" lumps banks,
            NBFCs and depositories together, very different businesses with
            very different index dynamics) to the closest real NSE sector
            index. Falls back to NIFTY FINANCIAL SERVICES (broader, includes
            NBFCs/capital markets/insurance) rather than forcing everything
            financial into NIFTY BANK, and to market-only comparison when no
            reasonable industry mapping exists at all.

Deliberately a static dict, not an LLM call — the benchmark used for a
quantitative comparison should be deterministic and auditable, not something
that can vary between calls for the same stock.
"""
from services.market_service import get_stock_price

MARKET_INDEX = "^NSEI"  # NIFTY 50

# Covers this codebase's currently-seen industries; extend as new ones show up.
# Values are Yahoo Finance tickers for NSE sector indices.
INDUSTRY_BENCHMARKS: dict[str, str] = {
    "Banks - Regional": "^NSEBANK",
    "Banks - Diversified": "^NSEBANK",
    "Auto Manufacturers": "^CNXAUTO",
    "Auto Parts": "^CNXAUTO",
    "Household & Personal Products": "^CNXFMCG",
    "Packaged Foods": "^CNXFMCG",
    "Confectioners": "^CNXFMCG",
    "Beverages - Non-Alcoholic": "^CNXFMCG",
    "Beverages - Brewers": "^CNXFMCG",
    "Tobacco": "^CNXFMCG",
    "Drug Manufacturers - Specialty & Generic": "^CNXPHARMA",
    "Drug Manufacturers - General": "^CNXPHARMA",
    "Biotechnology": "^CNXPHARMA",
    "Information Technology Services": "^CNXIT",
    "Software - Application": "^CNXIT",
    "Software - Infrastructure": "^CNXIT",
    # No dedicated NSE index — NIFTY FINANCIAL SERVICES is the closer fit than NIFTY BANK.
    "Capital Markets": "^CNXFIN",
    "Credit Services": "^CNXFIN",
    "Insurance - Life": "^CNXFIN",
    "Insurance - Diversified": "^CNXFIN",
    "Asset Management": "^CNXFIN",
    "Steel": "^CNXMETAL",
    "Other Industrial Metals & Mining": "^CNXMETAL",
    "Aluminum": "^CNXMETAL",
    "Real Estate - Development": "^CNXREALTY",
    "Real Estate Services": "^CNXREALTY",
}


async def _get_index_change_pct(symbol: str) -> float | None:
    """Indices are fetched through the same cached get_stock_price path as stocks."""
    data = await get_stock_price(symbol)
    return data.get("change_pct") if data else None


async def get_benchmark_context(industry: str | None, stock_change_pct: float) -> dict:
    """Market- and industry-relative performance for a stock's day move.
    industry_change_pct/industry_relative_pct are None when no mapping exists."""
    market_change = await _get_index_change_pct(MARKET_INDEX)
    industry_symbol = INDUSTRY_BENCHMARKS.get(industry) if industry else None
    industry_change = await _get_index_change_pct(industry_symbol) if industry_symbol else None

    return {
        "market_change_pct": market_change,
        "market_relative_pct": (
            round(stock_change_pct - market_change, 2) if market_change is not None else None
        ),
        "industry": industry,
        "industry_benchmark_symbol": industry_symbol,
        "industry_change_pct": industry_change,
        "industry_relative_pct": (
            round(stock_change_pct - industry_change, 2) if industry_change is not None else None
        ),
    }
