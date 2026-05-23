"""
Market data service with Redis caching.
NAV: 4-hour TTL. Stock prices: 15-minute TTL. Macro: 1-hour TTL.
"""
import json
import httpx
import yfinance as yf
import redis.asyncio as aioredis
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
