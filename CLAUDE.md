# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Punji (পুঁজি) is an autonomous personal finance agent for Indian investors. It tracks MF, stocks, FDs, PPF, and NPS; computes XIRR and Monte Carlo goal projections; and runs an LLM multi-agent pipeline to answer questions, detect concentration risk, and send proactive alerts.

## Running locally

**Prerequisites:** A Docker daemon must be running (Docker Desktop, OrbStack, or Colima). Python 3.11 venv and Node deps are already installed.

```bash
# One-command start (Docker infra + backend + frontend):
bash start.sh

# Or individually:
docker-compose up -d                               # Postgres 15 + Redis 7
cd backend && .venv/bin/alembic upgrade head       # Run migrations
cd backend && .venv/bin/uvicorn main:app --reload  # FastAPI on :8000
cd frontend && npm run dev                         # Next.js on :3000
```

API docs: http://localhost:8000/docs

## Backend commands

All commands run from `backend/` using the venv:

```bash
.venv/bin/uvicorn main:app --reload                          # Run server
.venv/bin/alembic upgrade head                               # Apply migrations
.venv/bin/alembic revision --autogenerate -m "description"   # New migration
.venv/bin/alembic downgrade -1                               # Rollback one
.venv/bin/python -c "import main; print('ok')"               # Smoke test
.venv/bin/pip install -r requirements.txt                    # Install deps
```

## Frontend commands

All commands run from `frontend/`:

```bash
npm run dev      # Dev server on :3000
npm run build    # Production build (tsc + next build)
npx tsc --noEmit # Type-check only
npm run lint
```

## Architecture overview

### Backend (`backend/`)

**Entry point:** `main.py` — FastAPI app with CORS middleware, all routers registered, APScheduler lifespan, and a WebSocket endpoint at `/ws/{user_id}?token=...`.

**Layered structure:**

```
routers/     → HTTP handlers (thin — validate, call service, return)
services/    → Business logic (no HTTP concerns)
agents/      → LLM pipeline (called only from routers/agent.py)
llm/         → Provider-agnostic LLM abstraction layer
models/      → SQLAlchemy ORM (async, PostgreSQL)
instruments/ → Per-instrument price refresh logic
importers/   → CSV parsers for broker formats
scheduler/   → APScheduler cron jobs
connectors/  → Broker API connectors (stubs only — not implemented)
```

**Database:** Async SQLAlchemy 2.0 with asyncpg. `get_db()` in `database.py` is the FastAPI dependency. All monetary amounts are stored as **rupees (`Numeric(15,2)`)** — no conversion needed at display time. The `holdings.metadata` column is JSONB and holds instrument-specific fields (scheme code for MF, exchange for stocks, maturity date for FD, etc.).

**Auth:** JWT (HS256) via `python-jose`. `dependencies.py::get_current_user()` is the FastAPI dependency used on all protected routes. Tokens are issued at login/register and refreshed via `/api/auth/refresh`.

**LLM abstraction layer** (`llm/`):
- `llm/registry.py` is the **only file to edit when swapping models** — assigns a provider instance to each of the 8 agent roles
- `llm/base.py` — `BaseLLMProvider` ABC with `generate()`, `generate_json()`, `as_langchain_llm()`
- `llm/providers/gemini.py` — Google AI Studio API key (local dev, free)
- `llm/providers/vertex.py` — Vertex AI (production on Cloud Run, no key needed)
- `llm/providers/anthropic.py` — Claude (optional swap-in, not default)
- When `ENVIRONMENT=production`, registry auto-routes to VertexAI; otherwise uses GeminiProvider
- Agents import `from llm import ORCHESTRATOR` etc. — zero direct SDK imports in agent files

**Agent pipeline** (`agents/orchestrator.py`):
1. `detect_intent()` — classifies user query into one of 9 intent categories via `ORCHESTRATOR.generate()`
2. `INTENT_ROUTING` dict maps each intent to an ordered list of agent names
3. Each agent mutates the `PunjiState` TypedDict and passes it to the next
4. `synthesise_response()` — generates the final user-facing answer from accumulated state

**Agent roles and model assignments** (in `llm/registry.py`):
- `ORCHESTRATOR`, `RECOMMENDATION`, `MARKET_INTELLIGENCE` → `gemini-1.5-pro` (user-facing, best quality)
- `DEVIL_ADVOCATE`, `PROACTIVE_ALERT`, `NEWS_INTELLIGENCE`, `GOAL_TRACKER`, `CONCENTRATION_RISK` → `gemini-1.5-flash` (background, fast/cheap)

**Market data:** `services/market_service.py` fetches MF NAVs from MFAPI.in (no key needed, 4h Redis TTL) and stock prices from yfinance (15min TTL). Redis keys follow `nav:{scheme_code}` and `stock:{symbol}` patterns.

**XIRR:** `services/portfolio_service.py::compute_xirr()` uses `scipy.optimize.brentq`. Sign convention: positive = outflow (buys/deposits), negative = inflow (sells/maturities). The terminal cashflow is the current market value added as a negative.

**Scheduled jobs** (`scheduler/jobs.py`): midnight portfolio snapshots, 8 AM IST proactive alerts, Sunday 2 AM Monte Carlo re-simulation for all goals, 1st-of-month AMFI composition refresh.

**Import pipeline:** `routers/imports.py` receives file upload → `importers/__init__.py::detect_format()` identifies broker by CSV headers → appropriate `CSVImporter` subclass parses to `HoldingDTO`/`TransactionDTO` → preview stored in import_jobs → confirm endpoint writes to DB with deduplication. Supported formats: Zerodha, Groww, CAMS, KFIN, generic CSV.

### Frontend (`frontend/`)

**Framework:** Next.js 16 App Router with TypeScript and Tailwind CSS v4. shadcn/ui style is `base-nova` (uses `@base-ui/react` primitives, not Radix).

**Auth:** NextAuth v5 (`next-auth@^5.0.0-beta`) with Google provider at `app/api/auth/[...nextauth]/route.ts`. Uses `export const { GET, POST } = handlers` (v5 pattern — not the v4 `export { handler as GET, handler as POST }`). On Google sign-in, calls backend `/api/auth/google` to exchange the Google ID token for a Punji JWT.

**Auth guard:** All authenticated pages (`/dashboard`, `/holdings`, `/goals`, `/alerts`, `/chat`, `/scenarios`, `/settings`) have a `layout.tsx` that renders `<AuthGuard>`, which redirects to `/login` if no user in Zustand store.

**State:** Zustand (`store/index.ts`), persisted to localStorage. Stores: `user`, `accessToken`, `portfolioSummary`, `liveAlerts` (pushed via WebSocket), `theme`.

**API client:** `lib/api.ts` — typed fetch wrapper. All endpoints use `Bearer` token from Zustand store. `streamChat()` in the same file is the SSE function for the chat page — reads a streaming response and fires callbacks for `token`, `reasoning_trace`, `done`, and `error` event types.

**WebSocket:** `lib/websocket.ts` connects to `ws://localhost:8000/ws/{userId}?token=...` for real-time alert pushes. The `usePunji().pushAlert()` action adds incoming alerts to `liveAlerts`.

**Theme:** `ThemeProvider` from `next-themes` wraps the app (attribute="class", defaultTheme="dark"). `ThemeToggle` component in topbar. `useChartColors()` hook (`lib/useChartColors.ts`) returns theme-aware colours for Recharts.

**Design tokens** (defined in `app/globals.css`):
- `--punji-brand`: #6366F1 (indigo) — primary accent
- `--punji-gain` / `--punji-loss`: green #22C55E / red #EF4444
- Use `text-green-400` / `text-red-400` for gain/loss text in Tailwind

**Charts:** Recharts 3. `Tooltip formatter` must accept `(v: unknown) => ...` and cast to `Number(v)` — Recharts v3 types pass `ValueType | undefined`.

**Pages built:**

| Route | What it does |
|---|---|
| `/login` | Email/password form + Google OAuth button |
| `/register` | Zod-validated registration form |
| `/onboarding` | 3-step: risk profile → goals → first CSV import |
| `/dashboard` | Portfolio metrics, 1Y area chart, allocation donut, recent alerts, quick-ask |
| `/holdings` | Tab filter by type, drag-drop CSV import (upload→preview→confirm), expandable rows, refresh/delete |
| `/goals` | SVG progress rings (Monte Carlo %), create/edit goals, re-simulate |
| `/alerts` | Inbox with severity badges, thumbs up/down feedback, mark-all-read |
| `/chat` | SSE streaming responses, reasoning trace accordion, conversation history sidebar |
| `/scenarios` | Preset + custom what-if inputs, P10/P50/P90 Monte Carlo results per goal |
| `/settings` | Profile, theme (dark/light/system), agent memory management, import history, danger zone |

## Working style

- **Always ask before assuming.** If a task has ambiguity — about scope, behaviour, edge cases, or intent — ask a clarifying question before writing any code. Do not make assumptions and proceed; the cost of a wrong assumption is higher than the cost of one question.
- This applies especially to: data model changes, deletions, migrations, UI behaviour, and anything that affects existing user data.

## Design principles

Follow these principles when designing or extending any part of the codebase.

- Follow SOLID principles, especially **Open/Closed** (OCP) and **Dependency Inversion** (DIP).
- Before writing a service, identify what is likely to vary in the future and isolate it behind an interface.
- Assume external integrations (communication, payments, storage, auth, search, data providers, broker connectors, etc.) will have multiple implementations over time.
- Depend on abstractions, not concrete implementations.
- Prefer extensible designs over minimal code — a new implementation should be addable with minimal or no changes to existing business logic.
- Prefer **Strategy Pattern** for varying behaviour and **Factory/Registry Pattern** for implementation selection.
- Avoid hard-coded provider-specific logic and large if-else/switch chains for choosing implementations.

**Before finalising any design, answer:**

1. What are the extension points?
2. How would a new implementation be added?
3. What existing code would remain unchanged?

## Key conventions

- **Monetary values:** Stored as **rupees** (`Numeric(15,2)`) in the DB and returned as rupees from the API. The `fmt()` helper in each page component handles lakh/crore formatting directly on the rupee value — no division needed.
- **Soft delete:** Holdings are deactivated (`is_active = false`), never hard-deleted.
- **Instrument metadata:** Never add new columns to `holdings` for instrument-specific fields — put them in `metadata_` (JSONB). The Python attribute is `metadata_` but maps to the `"metadata"` column via `mapped_column("metadata", ...)`.
- **UUID primary keys:** All models use `UUID(as_uuid=True)` with Python `uuid.uuid4` defaults.
- **Model imports:** Import models from the package `from models import User, Holding, ...` (not individual files) — `models/__init__.py` re-exports all.
- **LLM calls:** Never import provider SDKs (anthropic, google.generativeai, vertexai) directly in agent files. Always use `from llm import AGENT_ROLE` and call `await AGENT_ROLE.generate(prompt)` or `await AGENT_ROLE.generate_json(prompt)`.

## Environment variables

Backend `backend/.env`:
- `DATABASE_URL` — must use `postgresql+asyncpg://` scheme
- `REDIS_URL` — `redis://localhost:6379`
- `GOOGLE_AI_API_KEY` — from aistudio.google.com (free, used locally by GeminiProvider)
- `ANTHROPIC_API_KEY` — optional, only needed if swapping an agent to Claude in registry.py
- `JWT_SECRET` — any random string for local dev
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — for Google OAuth backend token verification
- `GCP_PROJECT_ID`, `GCP_REGION` — only needed in production (Vertex AI)
- `ENVIRONMENT` — `"development"` (local) or `"production"` (Cloud Run)
- `QDRANT_URL`, `QDRANT_API_KEY` — for agent memory; agents degrade gracefully if unreachable
- `RBI_REPO_RATE` — current RBI repo rate in percent, updated manually

Frontend `frontend/.env.local`:
- `NEXT_PUBLIC_API_URL` — `http://localhost:8000`
- `NEXT_PUBLIC_WS_URL` — `ws://localhost:8000`
- `NEXTAUTH_URL` — `http://localhost:3000`
- `NEXTAUTH_SECRET` — random string, signs NextAuth session tokens
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — read by NextAuth for Google provider

## GCP deployment

- `backend/Dockerfile` — Cloud Run compatible, runs `alembic upgrade head` then uvicorn on `$PORT`
- `cloudbuild.yaml` — builds backend image, pushes to Artifact Registry, deploys to Cloud Run `asia-south1`
- Production uses Vertex AI (same Gemini models, authenticated via Cloud Run service account — no API key needed)
- GCP infra (Cloud SQL, Memorystore, Secret Manager) is not needed for local development
