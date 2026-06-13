"""
Concentration risk computation.
Part A: Simple threshold checks (stock, sector, group).
Part B: Cross-instrument hidden exposure detection.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import FundComposition, BusinessGroupMapping
from services.instrument_service import get_all_instruments
from datetime import date


async def compute_concentration(db: AsyncSession, user_id) -> dict:
    holdings = await get_all_instruments(db, user_id)

    total = sum(h.current_value for h in holdings)
    if total == 0:
        return {"stocks": [], "sectors": [], "groups": [], "fund_overlaps": [], "hidden_exposure": []}

    # Part A: Direct stock concentration
    stocks = []
    for h in holdings:
        if h.instrument_type == "stock":
            pct = round(h.current_value / total * 100, 2)
            stocks.append({
                "symbol": h.metadata_.get("symbol", h.display_name),
                "name": h.display_name,
                "value": h.current_value,
                "portfolio_pct": pct,
                "alert_triggered": pct > 10,
            })
    stocks.sort(key=lambda x: x["portfolio_pct"], reverse=True)

    # Part A: Sector concentration
    sector_map: dict[str, int] = {}
    for h in holdings:
        if h.instrument_type == "stock":
            sector = h.metadata_.get("sector", "Unknown")
            sector_map[sector] = sector_map.get(sector, 0) + h.current_value
    sectors = [
        {"sector": s, "value": v, "portfolio_pct": round(v / total * 100, 2), "alert_triggered": v / total > 0.30}
        for s, v in sorted(sector_map.items(), key=lambda x: -x[1])
    ]

    # Part A: Business group concentration
    bgm_result = await db.execute(select(BusinessGroupMapping))
    bgm_list = bgm_result.scalars().all()
    isin_to_group = {b.company_isin: b.group_name for b in bgm_list}

    group_map: dict[str, int] = {}
    for h in holdings:
        isin = h.metadata_.get("isin", "")
        group = isin_to_group.get(isin)
        if group:
            group_map[group] = group_map.get(group, 0) + h.current_value
        # FDs with a known bank
        if h.instrument_type == "fixed_deposit":
            bank = h.metadata_.get("bank_name", "")
            for b in bgm_list:
                if bank.lower() in b.company_name.lower():
                    group_map[b.group_name] = group_map.get(b.group_name, 0) + h.current_value
                    break

    groups = [
        {"group_name": g, "value": v, "portfolio_pct": round(v / total * 100, 2), "alert_triggered": v / total > 0.25}
        for g, v in sorted(group_map.items(), key=lambda x: -x[1])
    ]

    # Part B: Hidden cross-instrument exposure
    hidden_exposure = await _compute_hidden_exposure(db, holdings, total, isin_to_group)

    return {
        "stocks": stocks,
        "sectors": sectors,
        "groups": groups,
        "fund_overlaps": await _compute_fund_overlaps(db, holdings),
        "hidden_exposure": hidden_exposure,
        "underperformers": await _compute_underperformers(holdings),
    }


async def _compute_hidden_exposure(db, holdings, total, isin_to_group) -> list[dict]:
    """Compute real company/group exposure across all three layers."""
    exposure_map: dict[str, dict] = {}  # isin/group_name -> {total_pct, breakdown}

    # Layer 1: Direct stock holdings
    for h in holdings:
        if h.instrument_type == "stock":
            isin = h.metadata_.get("isin", "")
            if not isin:
                continue
            pct = h.current_value / total * 100
            key = isin
            if key not in exposure_map:
                exposure_map[key] = {
                    "entity_name": h.display_name,
                    "entity_type": "company",
                    "total_real_exposure_pct": 0.0,
                    "breakdown": [],
                    "fd_equity_overlap": False,
                }
            exposure_map[key]["total_real_exposure_pct"] += pct
            exposure_map[key]["breakdown"].append({
                "source": f"Direct: {h.display_name}",
                "instrument_type": "stock",
                "holding_name": h.display_name,
                "exposure_pct": round(pct, 2),
                "computation": f"{round(h.current_value / 100):,} / portfolio",
            })

    # Layer 2: Indirect via mutual funds
    today_first = date.today().replace(day=1)
    for h in holdings:
        if h.instrument_type != "mutual_fund":
            continue
        scheme_code = h.metadata_.get("scheme_code")
        if not scheme_code:
            continue

        fund_pct = h.current_value / total

        comp_result = await db.execute(
            select(FundComposition)
            .where(
                FundComposition.scheme_code == scheme_code,
                FundComposition.disclosure_month <= today_first,
            )
            .order_by(FundComposition.disclosure_month.desc())
            .limit(50)
        )
        compositions = comp_result.scalars().all()

        for comp in compositions:
            indirect_pct = fund_pct * float(comp.weight_pct) / 100 * 100
            key = comp.company_isin
            if key not in exposure_map:
                exposure_map[key] = {
                    "entity_name": comp.company_name,
                    "entity_type": "company",
                    "total_real_exposure_pct": 0.0,
                    "breakdown": [],
                    "fd_equity_overlap": False,
                }
            exposure_map[key]["total_real_exposure_pct"] += indirect_pct
            exposure_map[key]["breakdown"].append({
                "source": f"Via {h.display_name}",
                "instrument_type": "mutual_fund",
                "holding_name": h.display_name,
                "exposure_pct": round(indirect_pct, 2),
                "computation": f"{comp.weight_pct}% of fund × {round(fund_pct * 100, 1)}% portfolio allocation",
            })

    # Layer 3: FD institutional exposure + equity overlap check
    for h in holdings:
        if h.instrument_type != "fixed_deposit":
            continue
        bank_name = h.metadata_.get("bank_name", "")
        fd_pct = h.current_value / total * 100

        # Check if user also holds equity of same institution
        has_equity_overlap = any(
            hh.instrument_type == "stock" and bank_name.lower() in hh.display_name.lower()
            for hh in holdings
        )

        if has_equity_overlap:
            for key, exp in exposure_map.items():
                if bank_name.lower() in exp["entity_name"].lower():
                    exp["fd_equity_overlap"] = True
                    exp["total_real_exposure_pct"] += fd_pct
                    exp["breakdown"].append({
                        "source": f"FD institutional exposure",
                        "instrument_type": "fd",
                        "holding_name": h.display_name,
                        "exposure_pct": round(fd_pct, 2),
                        "computation": "FD institutional counterparty risk",
                    })

    # Filter to entities above warning threshold (8%) and sort
    result = []
    for key, exp in exposure_map.items():
        exp["total_real_exposure_pct"] = round(exp["total_real_exposure_pct"], 2)
        exp["alert_triggered"] = exp["total_real_exposure_pct"] > 12
        if exp["total_real_exposure_pct"] >= 5:
            result.append(exp)

    return sorted(result, key=lambda x: -x["total_real_exposure_pct"])


async def _compute_fund_overlaps(db, holdings) -> list[dict]:
    mf_holdings = [h for h in holdings if h.instrument_type == "mutual_fund" and h.metadata_.get("scheme_code")]
    if len(mf_holdings) < 2:
        return []

    today_first = date.today().replace(day=1)
    fund_isins: dict[int, set[str]] = {}

    for h in mf_holdings:
        sc = h.metadata_["scheme_code"]
        result = await db.execute(
            select(FundComposition.company_isin)
            .where(
                FundComposition.scheme_code == sc,
                FundComposition.disclosure_month <= today_first,
            )
            .order_by(FundComposition.disclosure_month.desc())
            .limit(10)  # top-10 holdings
        )
        fund_isins[sc] = set(result.scalars().all())

    overlaps = []
    for i, h1 in enumerate(mf_holdings):
        for h2 in mf_holdings[i + 1:]:
            sc1, sc2 = h1.metadata_["scheme_code"], h2.metadata_["scheme_code"]
            s1, s2 = fund_isins.get(sc1, set()), fund_isins.get(sc2, set())
            if not s1 or not s2:
                continue
            intersection = s1 & s2
            overlap_pct = round(len(intersection) / min(len(s1), len(s2)) * 100, 1)
            if overlap_pct > 30:
                overlaps.append({
                    "fund1": h1.display_name,
                    "fund2": h2.display_name,
                    "overlap_pct": overlap_pct,
                })
    return overlaps


async def _compute_underperformers(holdings) -> list[dict]:
    """Compare stock returns vs sector index over 3 months."""
    import yfinance as yf
    results = []
    sector_index_map = {
        "Banking": "^NSEBANK",
        "Financial Services": "^NSEBANK",
        "Information Technology": "^CNXIT",
        "FMCG": "^CNXFMCG",
        "Pharma": "^CNXPHARMA",
        "Auto": "^CNXAUTO",
        "Energy": "^CNXENERGY",
        "Metal": "^CNXMETAL",
    }

    for h in holdings:
        if h.instrument_type != "stock":
            continue
        symbol = h.metadata_.get("symbol", "")
        sector = h.metadata_.get("sector", "")
        if not symbol or not sector:
            continue

        try:
            stock_hist = yf.Ticker(symbol).history(period="3mo")
            if stock_hist.empty:
                continue
            stock_return = (stock_hist["Close"].iloc[-1] - stock_hist["Close"].iloc[0]) / stock_hist["Close"].iloc[0] * 100

            sector_idx = sector_index_map.get(sector)
            if sector_idx:
                sector_hist = yf.Ticker(sector_idx).history(period="3mo")
                if not sector_hist.empty:
                    sector_return = (sector_hist["Close"].iloc[-1] - sector_hist["Close"].iloc[0]) / sector_hist["Close"].iloc[0] * 100
                    underperformance = sector_return - stock_return
                    if underperformance > 15:
                        results.append({
                            "symbol": symbol,
                            "name": h.display_name,
                            "stock_return_3m": round(stock_return, 2),
                            "sector_return_3m": round(sector_return, 2),
                            "underperformance_pct": round(underperformance, 2),
                        })
        except Exception:
            continue

    return results
