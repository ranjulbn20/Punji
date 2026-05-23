"""WebSocket connection manager for real-time push notifications."""
from fastapi import WebSocket
from typing import Any


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}  # type: ignore[type-arg]

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self._connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket):
        if user_id in self._connections:
            self._connections[user_id] = [
                ws for ws in self._connections[user_id] if ws != websocket
            ]

    async def send_to_user(self, user_id: str, message: Any):
        import json
        for ws in self._connections.get(user_id, []):
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                pass


manager = ConnectionManager()
