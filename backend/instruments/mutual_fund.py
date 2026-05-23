import httpx
from .base import InstrumentHandler


class MutualFundHandler(InstrumentHandler):
    def asset_class(self) -> str:
        return "equity"  # overridden per fund category at import time

    async def fetch_current_value(self, metadata: dict) -> int | None:
        scheme_code = metadata.get("scheme_code")
        units = metadata.get("units")
        if not scheme_code or not units:
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"https://api.mfapi.in/mf/{scheme_code}")
            if resp.status_code != 200:
                return None
            data = resp.json()
            nav = float(data["data"][0]["nav"])
            return int(nav * float(units) * 100)  # store in paise
        except Exception:
            return None

    async def fetch_nav(self, scheme_code: int) -> float | None:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"https://api.mfapi.in/mf/{scheme_code}")
            if resp.status_code != 200:
                return None
            return float(resp.json()["data"][0]["nav"])
        except Exception:
            return None
