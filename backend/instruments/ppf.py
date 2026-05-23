from .base import InstrumentHandler


class PPFHandler(InstrumentHandler):
    """Stub — PPF balance is manually updated by the user. No live refresh."""

    def asset_class(self) -> str:
        return "debt"

    async def fetch_current_value(self, metadata: dict) -> int | None:
        return None
