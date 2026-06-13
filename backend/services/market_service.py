"""
Market data service with Redis caching.
NAV: 4-hour TTL. Stock prices: 15-minute TTL. Macro: 1-hour TTL.
"""
import json
import httpx
import yfinance as yf
import redis.asyncio as aioredis
from datetime import datetime, timezone, timedelta
from config import settings


def get_redis():
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def get_mf_nav(scheme_code: int) -> dict | None:
    r = get_redis()
    key = f"nav:{scheme_code}"
    try:
        cached = await r.get(key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://api.mfapi.in/mf/{scheme_code}")
        if resp.status_code != 200:
            return None
        data = resp.json()
        result = {
            "scheme_name": data.get("meta", {}).get("scheme_name", ""),
            "current_nav": float(data["data"][0]["nav"]),
            "nav_date": data["data"][0]["date"],
            "fund_house": data.get("meta", {}).get("fund_house", ""),
            "category": data.get("meta", {}).get("scheme_category", ""),
        }
        try:
            await r.setex(key, 14400, json.dumps(result))  # 4-hour TTL
        except Exception:
            pass
        return result
    except Exception:
        return None
    finally:
        await r.aclose()


async def get_stock_price(symbol: str) -> dict | None:
    r = get_redis()
    key = f"stock:{symbol}"
    try:
        cached = await r.get(key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        result = {
            "symbol": symbol,
            "current_price": info.last_price,
            "change_pct": round((info.last_price - info.previous_close) / info.previous_close * 100, 2)
            if info.previous_close else None,
        }
        try:
            await r.setex(key, 900, json.dumps(result))  # 15-min TTL
        except Exception:
            pass
        return result
    except Exception:
        return None
    finally:
        await r.aclose()


async def get_macro_data() -> dict:
    r = get_redis()
    key = "macro:india"
    try:
        cached = await r.get(key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    result = {"repo_rate": settings.rbi_repo_rate}
    try:
        nifty = yf.Ticker("^NSEI")
        hist = nifty.history(period="5d")
        if not hist.empty:
            result["nifty50_level"] = round(float(hist["Close"].iloc[-1]), 2)
        # Nifty P/E from yfinance info (may not be available for index)
        result["nifty50_pe"] = None
    except Exception:
        result["nifty50_level"] = None

    try:
        await r.setex(key, 3600, json.dumps(result))
    except Exception:
        pass

    try:
        await r.aclose()
    except Exception:
        pass
    return result


_AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
_AMFI_MAP_KEY = "amfi:isin_map"
_AMFI_NAME_MAP_KEY = "amfi:name_map"
_AMFI_TTL = 6 * 3600  # 6 hours


def _normalise_scheme_name(name: str) -> str:
    """Lower-case, collapse whitespace, strip punctuation for fuzzy matching."""
    import re
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9 ]", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name


async def _build_amfi_maps() -> tuple[dict, dict]:
    """Download AMFI NAVAll.txt. Returns (isin_map, name_map) where both map to
    {scheme_code, scheme_name, isin, current_nav, nav_date}."""
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(_AMFI_URL)
    isin_map: dict = {}
    name_map: dict = {}
    for line in resp.text.splitlines():
        parts = line.strip().split(";")
        if len(parts) < 6:
            continue
        try:
            scheme_code = int(parts[0].strip())
            nav = float(parts[4].strip())
        except (ValueError, TypeError):
            continue
        isin1, isin2 = parts[1].strip(), parts[2].strip()
        scheme_name = parts[3].strip()
        primary_isin = isin1 if (isin1 and isin1 != "-") else (isin2 if (isin2 and isin2 != "-") else "")
        entry = {
            "scheme_code": scheme_code,
            "scheme_name": scheme_name,
            "isin": primary_isin,
            "current_nav": nav,
            "nav_date": parts[5].strip(),
        }
        if isin1 and isin1 != "-":
            isin_map[isin1] = entry
        if isin2 and isin2 != "-":
            isin_map[isin2] = entry
        norm = _normalise_scheme_name(scheme_name)
        if norm:
            name_map[norm] = entry
    return isin_map, name_map


async def _load_amfi_maps(r) -> tuple[dict, dict]:
    """Return (isin_map, name_map), fetching from AMFI if not cached."""
    raw_isin = await r.get(_AMFI_MAP_KEY)
    raw_name = await r.get(_AMFI_NAME_MAP_KEY)
    if raw_isin and raw_name:
        return json.loads(raw_isin), json.loads(raw_name)
    isin_map, name_map = await _build_amfi_maps()
    try:
        await r.setex(_AMFI_MAP_KEY, _AMFI_TTL, json.dumps(isin_map))
        await r.setex(_AMFI_NAME_MAP_KEY, _AMFI_TTL, json.dumps(name_map))
    except Exception:
        pass
    return isin_map, name_map


async def get_nav_by_isin(isin: str) -> dict | None:
    """Look up a mutual fund by ISIN using the AMFI NAVAll.txt master file."""
    r = get_redis()
    isin_key = f"isin:{isin}"
    try:
        cached = await r.get(isin_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    try:
        isin_map, _ = await _load_amfi_maps(r)
        result = isin_map.get(isin)
        if result:
            try:
                await r.setex(isin_key, _AMFI_TTL, json.dumps(result))
            except Exception:
                pass
        return result
    except Exception:
        return None
    finally:
        await r.aclose()


async def get_nav_by_name(scheme_name: str) -> dict | None:
    """Fallback: look up a mutual fund by normalised scheme name from AMFI data."""
    r = get_redis()
    try:
        _, name_map = await _load_amfi_maps(r)
        norm = _normalise_scheme_name(scheme_name)
        return name_map.get(norm)
    except Exception:
        return None
    finally:
        await r.aclose()


async def search_mf(query: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.mfapi.in/mf/search", params={"q": query})
        if resp.status_code != 200:
            return []
        data = resp.json()
        return [
            {
                "scheme_code": item.get("schemeCode"),
                "scheme_name": item.get("schemeName"),
                "fund_house": item.get("fundHouse", ""),
            }
            for item in data[:20]
        ]
    except Exception:
        return []


_REFRESH_COOLDOWN = timedelta(minutes=30)


async def refresh_mf_navs_for_user(db, user_id) -> int:
    """
    Fetch latest NAVs from AMFI for all active MF holdings and update
    current_nav + current_value in the DB.

    Skips the refresh if every holding was updated within the last 30 minutes
    (guards against repeated logins in quick succession).

    Returns the number of holdings updated.
    """
    from sqlalchemy import select
    from models import MutualFund

    result = await db.execute(
        select(MutualFund).where(
            MutualFund.user_id == user_id,
            MutualFund.is_active == True,
        )
    )
    holdings = result.scalars().all()
    if not holdings:
        return 0

    # Skip if all holdings were refreshed recently
    cutoff = datetime.now(timezone.utc) - _REFRESH_COOLDOWN
    if all(
        mf.last_refreshed_at and mf.last_refreshed_at.replace(tzinfo=timezone.utc) > cutoff
        for mf in holdings
    ):
        return 0

    now = datetime.now(timezone.utc)
    updated = 0
    for mf in holdings:
        if mf.isin:
            nav_data = await get_nav_by_isin(mf.isin)
        else:
            # Fallback: match by scheme name (covers holdings imported before ISIN fix)
            nav_data = await get_nav_by_name(mf.scheme_name or mf.display_name)

        if not nav_data:
            continue
        mf.current_nav = nav_data["current_nav"]
        mf.current_value = round(float(mf.units) * nav_data["current_nav"], 2)
        mf.last_refreshed_at = now
        if nav_data.get("scheme_code") and not mf.scheme_code:
            mf.scheme_code = nav_data["scheme_code"]
        # Backfill ISIN if we found it via name match
        if not mf.isin and nav_data.get("isin"):
            mf.isin = nav_data["isin"]
        updated += 1

    if updated:
        await db.commit()
    return updated


async def refresh_mf_navs_bg(user_id: str) -> None:
    """Background-task wrapper: creates its own DB session."""
    from database import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as db:
            count = await refresh_mf_navs_for_user(db, user_id)
            if count:
                print(f"[NAV refresh] Updated {count} MF holdings for user {user_id}")
    except Exception as e:
        print(f"[NAV refresh] Error for user {user_id}: {e}")


async def get_stock_news(symbol: str) -> list[dict]:
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news or []
        return [
            {
                "title": n.get("content", {}).get("title", ""),
                "publisher": n.get("content", {}).get("provider", {}).get("displayName", ""),
                "link": n.get("content", {}).get("canonicalUrl", {}).get("url", ""),
                "published_at": n.get("content", {}).get("pubDate", ""),
            }
            for n in news[:10]
        ]
    except Exception:
        return []
