from .base import InstrumentHandler


class NPSHandler(InstrumentHandler):
    """Stub — NPS balance is manually updated by the user. No live refresh."""

    def asset_class(self) -> str:
        return "equity"  # allocation depends on scheme preference

    async def fetch_current_value(self, metadata: dict) -> int | None:
        return None
