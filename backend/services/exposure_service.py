"""
Portfolio look-through / exposure computation.

Aggregates direct stock holdings and indirect MF holdings (via fund_compositions)
into a unified view by company and by sector.  This is intentionally separate from
concentration_service.py: that module detects risk thresholds and triggers alerts;
this one computes *allocation* for display.
"""
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import FundComposition
from services.instrument_service import get_all_instruments


async def compute_exposure(db: AsyncSession, user_id) -> dict:
    holdings = await get_all_instruments(db, user_id)

    total = sum(float(h.current_value) for h in holdings)
    if total == 0:
        return _empty_response()

    # ── stock-level map: isin → exposure accumulator ──────────────────────────
    stock_map: dict[str, dict] = {}
    # ── sector map: sector_name → {direct, indirect} ─────────────────────────
    sector_map: dict[str, dict] = {}
    # ── MFs without any composition data ─────────────────────────────────────
    mf_without_composition: list[dict] = []

    # ─── Layer 1: direct stock holdings ───────────────────────────────────────
    for h in holdings:
        if h.instrument_type != "stock":
            continue
        isin = h.metadata_.get("isin", "")
        sector = h.metadata_.get("sector") or "Unknown"
        pct = float(h.current_value) / total * 100

        _add_stock(stock_map, isin, h.display_name, sector, direct=pct)
        _add_sector(sector_map, sector, direct=pct)

    # ─── Layer 2: indirect via mutual fund underlying holdings ────────────────
    today_first = date.today().replace(day=1)

    mf_holdings = [h for h in holdings if h.instrument_type == "mutual_fund"]
    for h in mf_holdings:
        scheme_code = h.metadata_.get("scheme_code")
        if not scheme_code:
            mf_without_composition.append({
                "name": h.display_name,
                "pct_of_portfolio": round(float(h.current_value) / total * 100, 2),
            })
            continue

        comp_result = await db.execute(
            select(FundComposition)
            .where(
                FundComposition.scheme_code == scheme_code,
                FundComposition.disclosure_month <= today_first,
            )
            .order_by(FundComposition.disclosure_month.desc())
            .limit(100)
        )
        compositions = comp_result.scalars().all()

        if not compositions:
            mf_without_composition.append({
                "name": h.display_name,
                "pct_of_portfolio": round(float(h.current_value) / total * 100, 2),
            })
            continue

        fund_pct = float(h.current_value) / total
        for comp in compositions:
            indirect_pct = fund_pct * float(comp.weight_pct) / 100 * 100
            sector = comp.sector or "Unknown"
            _add_stock(
                stock_map, comp.company_isin, comp.company_name,
                sector, indirect=indirect_pct,
                source_label=h.display_name,
            )
            _add_sector(sector_map, sector, indirect=indirect_pct)

    # ─── Build sorted output ──────────────────────────────────────────────────
    by_stock = sorted(
        [_finalise_stock(v) for v in stock_map.values()],
        key=lambda x: -x["total_pct"],
    )
    by_sector = sorted(
        [_finalise_sector(s, v) for s, v in sector_map.items()],
        key=lambda x: -x["total_pct"],
    )

    last_comp_date: date | None = None
    if by_stock:
        last_comp_result = await db.execute(
            select(FundComposition.disclosure_month)
            .order_by(FundComposition.disclosure_month.desc())
            .limit(1)
        )
        row = last_comp_result.scalar_one_or_none()
        if row:
            last_comp_date = row

    return {
        "total_value": round(total, 2),
        "by_stock": by_stock,
        "by_sector": by_sector,
        "mf_without_composition": sorted(
            mf_without_composition, key=lambda x: -x["pct_of_portfolio"]
        ),
        "last_composition_date": last_comp_date.isoformat() if last_comp_date else None,
    }


# ── helpers ───────────────────────────────────────────────────────────────────

def _empty_response() -> dict:
    return {
        "total_value": 0,
        "by_stock": [],
        "by_sector": [],
        "mf_without_composition": [],
        "last_composition_date": None,
    }


def _add_stock(
    stock_map: dict,
    isin: str,
    name: str,
    sector: str,
    *,
    direct: float = 0.0,
    indirect: float = 0.0,
    source_label: str = "",
) -> None:
    if isin not in stock_map:
        stock_map[isin] = {
            "isin": isin,
            "name": name,
            "sector": sector,
            "direct_pct": 0.0,
            "indirect_pct": 0.0,
            "sources": [],
        }
    entry = stock_map[isin]
    if direct:
        entry["direct_pct"] += direct
        entry["sources"].append({
            "label": f"Direct: {name}",
            "pct": round(direct, 2),
            "instrument_type": "stock",
        })
    if indirect:
        entry["indirect_pct"] += indirect
        entry["sources"].append({
            "label": f"Via {source_label}",
            "pct": round(indirect, 2),
            "instrument_type": "mutual_fund",
        })


def _finalise_stock(entry: dict) -> dict:
    total = entry["direct_pct"] + entry["indirect_pct"]
    return {
        "isin": entry["isin"],
        "name": entry["name"],
        "sector": entry["sector"],
        "total_pct": round(total, 2),
        "direct_pct": round(entry["direct_pct"], 2),
        "indirect_pct": round(entry["indirect_pct"], 2),
        "sources": entry["sources"],
    }


def _add_sector(sector_map: dict, sector: str, *, direct: float = 0.0, indirect: float = 0.0) -> None:
    if sector not in sector_map:
        sector_map[sector] = {"direct": 0.0, "indirect": 0.0}
    sector_map[sector]["direct"] += direct
    sector_map[sector]["indirect"] += indirect


def _finalise_sector(sector: str, v: dict) -> dict:
    total = v["direct"] + v["indirect"]
    return {
        "sector": sector,
        "total_pct": round(total, 2),
        "direct_pct": round(v["direct"], 2),
        "indirect_pct": round(v["indirect"], 2),
    }
