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


async def _get_company_profile(symbol: str) -> dict:
    """Shared fetch behind get_company_name/get_stock_industry — one yfinance
    .info call cached 30 days (company name/industry essentially never change)
    instead of two separate ones."""
    r = get_redis()
    key = f"company_profile:{symbol}"
    try:
        cached = await r.get(key)
        if cached is not None:
            return json.loads(cached)
    except Exception:
        pass

    profile = {"name": symbol.split(".")[0], "industry": None}
    try:
        info = yf.Ticker(symbol).info
        profile["name"] = info.get("longName") or info.get("shortName") or profile["name"]
        profile["industry"] = info.get("industry")
    except Exception:
        pass

    try:
        await r.setex(key, 30 * 86400, json.dumps(profile))
    except Exception:
        pass
    finally:
        await r.aclose()
    return profile


async def get_company_name(symbol: str) -> str:
    """Resolves a ticker to its full legal name (e.g. GILLETTE.NS -> 'Gillette India Limited') —
    needed because a bare ticker like GILLETTE is too ambiguous to search news with."""
    profile = await _get_company_profile(symbol)
    return profile["name"]


async def get_stock_industry(symbol: str) -> str | None:
    """Yahoo's granular `industry` (e.g. 'Banks - Regional'), used for benchmark
    mapping in services/benchmark_service.py — deliberately not the broad `sector`
    field, which is too coarse (e.g. 'Financial Services' lumps banks, NBFCs and
    depositories together)."""
    profile = await _get_company_profile(symbol)
    return profile["industry"]


async def get_multi_day_change(symbol: str, days: int = 5) -> float | None:
    """N-trading-day % change (default 5D) — catches a slow bleed that no single
    day's move would cross a threshold for. Heavier than get_stock_price's
    fast_info ping, so cached separately with a longer TTL."""
    r = get_redis()
    key = f"stock_{days}d:{symbol}"
    try:
        cached = await r.get(key)
        if cached is not None:
            return json.loads(cached)
    except Exception:
        pass

    result = None
    try:
        hist = yf.Ticker(symbol).history(period=f"{days + 5}d")
        closes = hist["Close"].dropna()
        if len(closes) >= 2:
            latest = closes.iloc[-1]
            past = closes.iloc[max(0, len(closes) - 1 - days)]
            if past:
                result = round(float((latest - past) / past * 100), 2)
    except Exception:
        pass

    try:
        await r.setex(key, 4 * 3600, json.dumps(result))
    except Exception:
        pass
    finally:
        await r.aclose()
    return result


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


async def get_stock_sector(symbol: str) -> str | None:
    """Fetch sector for a stock symbol, cached in Redis for 7 days."""
    r = get_redis()
    key = f"sector:{symbol}"
    try:
        cached = await r.get(key)
        if cached:
            return cached if cached != "null" else None
    except Exception:
        pass
    finally:
        await r.aclose()

    try:
        info = yf.Ticker(symbol).info
        sector = info.get("sector") or info.get("industryDisp") or None
        r2 = get_redis()
        try:
            await r2.setex(key, 7 * 86400, sector if sector else "null")
        except Exception:
            pass
        finally:
            await r2.aclose()
        return sector
    except Exception:
        return None


async def refresh_stock_prices_for_user(db, user_id) -> int:
    """
    Fetch latest prices from yfinance for all active stock holdings and update
    current_price + current_value in the DB.

    Skips the refresh if every holding was updated within the last 30 minutes.

    Returns the number of holdings updated.
    """
    from sqlalchemy import select
    from models import Stock

    result = await db.execute(
        select(Stock).where(
            Stock.user_id == user_id,
            Stock.is_active == True,
        )
    )
    holdings = result.scalars().all()
    if not holdings:
        return 0

    cutoff = datetime.now(timezone.utc) - _REFRESH_COOLDOWN
    if all(
        s.last_refreshed_at and s.last_refreshed_at.replace(tzinfo=timezone.utc) > cutoff
        for s in holdings
    ):
        return 0

    now = datetime.now(timezone.utc)
    updated = 0
    for stock in holdings:
        price_data = await get_stock_price(stock.symbol)
        if not price_data or not price_data.get("current_price"):
            continue
        price = price_data["current_price"]
        stock.current_price = price
        stock.current_value = round(float(stock.quantity) * price, 2)
        stock.last_refreshed_at = now
        if stock.sector is None:
            stock.sector = await get_stock_sector(stock.symbol)
        updated += 1

    if updated:
        await db.commit()
    return updated


async def refresh_stock_prices_bg(user_id: str) -> None:
    """Background-task wrapper: creates its own DB session."""
    from database import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as db:
            count = await refresh_stock_prices_for_user(db, user_id)
            if count:
                print(f"[Stock refresh] Updated {count} stock holdings for user {user_id}")
    except Exception as e:
        print(f"[Stock refresh] Error for user {user_id}: {e}")


NEWS_MAX_AGE_DAYS = 7


async def get_stock_news(symbol: str) -> list[dict]:
    """Recent news only — yfinance's feed is sorted newest-first but includes
    articles months old for thinly-covered stocks, so anything past
    NEWS_MAX_AGE_DAYS is dropped rather than surfaced as if it just happened."""
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news or []
        cutoff = datetime.now(timezone.utc) - timedelta(days=NEWS_MAX_AGE_DAYS)

        items = []
        for n in news:
            content = n.get("content", {})
            pub_date = content.get("pubDate", "")
            try:
                published_at = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
            except ValueError:
                continue
            if published_at < cutoff:
                continue
            items.append({
                "title": content.get("title", ""),
                "publisher": content.get("provider", {}).get("displayName", ""),
                "link": content.get("canonicalUrl", {}).get("url", ""),
                "published_at": pub_date,
            })
        return items[:10]
    except Exception:
        return []
