import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError

from config import settings
from services.auth_service import decode_token
from services.websocket_service import manager
from scheduler.jobs import create_scheduler

from routers import auth, holdings, transactions, goals, alerts, portfolio, market, imports, agent, scenarios


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = create_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(
    title="Punji API",
    description="Autonomous Personal Finance Agent for Indian Investors",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(auth.router)
app.include_router(holdings.router)
app.include_router(transactions.router)
app.include_router(goals.router)
app.include_router(alerts.router)
app.include_router(portfolio.router)
app.include_router(market.router)
app.include_router(imports.router)
app.include_router(agent.router)
app.include_router(scenarios.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "punji-api"}


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, token: str = Query(...)):
    try:
        payload = decode_token(token)
        if payload.get("sub") != user_id:
            await websocket.close(code=4001)
            return
    except JWTError:
        await websocket.close(code=4001)
        return

    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "pong":
                pass  # heartbeat acknowledged
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
