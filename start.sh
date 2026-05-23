#!/bin/bash
# Punji local startup script
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# Free ports if already in use from a previous run
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
lsof -ti :3000 | xargs kill -9 2>/dev/null || true

echo "==> Starting PostgreSQL + Redis via Docker..."
docker-compose -f "$ROOT/docker-compose.yml" up -d

echo "==> Waiting for Postgres to be ready..."
until docker exec punji_postgres pg_isready -U punji -d punji &>/dev/null; do sleep 1; done
echo "    Postgres ready."

echo "==> Running Alembic migrations..."
cd "$BACKEND"
.venv/bin/python -m alembic upgrade head

echo "==> Starting FastAPI backend on :8000..."
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

echo "==> Starting Next.js frontend on :3000..."
cd "$FRONTEND"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "  Punji is running!"
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8000"
echo "  API docs: http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop all services."

trap "kill $BACKEND_PID $FRONTEND_PID; docker-compose -f '$ROOT/docker-compose.yml' stop" EXIT
wait
