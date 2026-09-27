"""
Google News RSS — unofficial, undocumented endpoint (no public API exists for
Google News). Free, no key. Chosen as the primary news source because it
aggregates across Indian publications (Moneycontrol, ET, LiveMint, etc.)
rather than relying on a single financial-data vendor's ticker mapping, which
gave much better coverage of NSE mid/small-caps in testing than yfinance or
a financial news aggregator would. Being unofficial, it could change format
or start rate-limiting without notice — that's what YFinanceNewsProvider in
fallback.py is for.
"""
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import httpx

from services.news_providers.base import BaseNewsProvider

MAX_AGE_DAYS = 7


class GoogleNewsRSSProvider(BaseNewsProvider):
    async def get_news(self, symbol: str, company_name: str) -> list[dict]:
        query = company_name or symbol
        url = (
            f"https://news.google.com/rss/search?q={quote(query)}+when:{MAX_AGE_DAYS}d"
            "&hl=en-IN&gl=IN&ceid=IN:en"
        )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
                response.raise_for_status()
            root = ET.fromstring(response.text)
        except Exception:
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
        items = []
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            pub_el = item.find("pubDate")
            source_el = item.find("source")
            if title_el is None or link_el is None or pub_el is None:
                continue

            try:
                published_at = parsedate_to_datetime(pub_el.text)
            except (TypeError, ValueError):
                continue
            if published_at < cutoff:
                continue

            publisher = source_el.text if source_el is not None else ""
            title = title_el.text or ""
            suffix = f" - {publisher}"
            if publisher and title.endswith(suffix):
                title = title[: -len(suffix)]

            items.append({
                "title": title,
                "publisher": publisher,
                "link": link_el.text,
                "published_at": pub_el.text,
            })

        return items[:10]
