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
- `llm/registry.py` is the **only file to edit when swapping models** — assigns a provider instance to each of the 8 agent roles, plus the shared `EMBEDDING` provider used for agent memory
- `llm/base.py` — `BaseLLMProvider` ABC with `generate()`, `generate_json()`, `as_langchain_llm()`. Both `generate()` and `generate_json()` take a `use_search: bool = False` param that grounds the response in live Google Search results where the provider supports it.
- `llm/providers/gemini.py` — Google AI Studio API key, used in every environment (local and production — there is no separate Vertex AI path). Uses the unified `google-genai` SDK (`google.generativeai` is deprecated — do not reintroduce it).
- `llm/providers/anthropic.py` — Claude (optional swap-in, not default). `use_search` is accepted for interface compatibility but not implemented — ignored rather than raising.
- `llm/providers/groq_provider.py` — Groq free tier (`openai/gpt-oss-120b` by default), used only as a fallback (see `llm/fallback.py`), never swapped in directly via registry. Groq's active model roster changes over time — check `client.models.list()` if this 404s again.
- `llm/fallback.py` — `FallbackLLMProvider` wraps any primary `BaseLLMProvider` and retries against a fallback provider if the primary raises. Composable over any provider pair, not just Gemini/Groq.
- `llm/retry.py` — retries Gemini calls on transient `429`/`503` google-genai errors with exponential backoff, before `FallbackLLMProvider` would ever kick in.
- `llm/embeddings/` — `BaseEmbeddingProvider` ABC + `GeminiEmbeddingProvider` (`text-embedding-004`). Used by `agents/memory.py` for agent-memory semantic search (Qdrant). Same swap-one-line pattern as the LLM roles: change the `EMBEDDING` assignment in `registry.py` to swap embedding models.
- Agents import `from llm import ORCHESTRATOR` etc. — zero direct SDK imports in agent files

**Agent pipeline** (`agents/orchestrator.py`):
1. `detect_intent()` — classifies user query into one of 9 intent categories via `ORCHESTRATOR.generate()`
2. `INTENT_ROUTING` dict maps each intent to an ordered list of agent names
3. Each agent mutates the `PunjiState` TypedDict and passes it to the next
4. `synthesise_response()` — generates the final user-facing answer from accumulated state

**Agent roles and model assignments** (in `llm/registry.py`):
- `ORCHESTRATOR`, `RECOMMENDATION`, `MARKET_INTELLIGENCE` → `gemini-flash-latest` (user-facing; the `-latest` alias auto-tracks Google's newest Flash release). `MARKET_INTELLIGENCE` and `RECOMMENDATION` call with `use_search=True` for live-grounded answers.
- `DEVIL_ADVOCATE`, `PROACTIVE_ALERT`, `NEWS_INTELLIGENCE`, `GOAL_TRACKER`, `CONCENTRATION_RISK` → `gemini-1.5-flash` (background, fast/cheap)

**Market data:** `services/market_service.py` fetches MF NAVs from MFAPI.in (no key needed, 4h Redis TTL) and stock prices from yfinance (15min TTL). Redis keys follow `nav:{scheme_code}` and `stock:{symbol}` patterns.

**XIRR:** `services/portfolio_service.py::compute_xirr()` uses `scipy.optimize.brentq`. Sign convention: positive = outflow (buys/deposits), negative = inflow (sells/maturities). The terminal cashflow is the current market value added as a negative.

**Scheduled jobs** (`scheduler/jobs.py`): midnight portfolio snapshots, 8 AM IST proactive alerts (portfolio-level: drift/FD maturity/goal risk/concentration), market signal check every ~2-3h on weekdays 10am-3pm IST (see below), Sunday 2 AM Monte Carlo re-simulation for all goals, 1st-of-month AMFI composition refresh.

**Proactive signal engine — Phase 1** (`services/signal_service.py`, `services/benchmark_service.py`, `agents/proactive_alert.py::run_market_signal_check_for_user`): a portfolio-monitoring system distinct from the news highlights feature below — detects and explains "something happened". Signals feed a **deterministic** fusion — no LLM spent combining them, only on reading news text:
- **Price signal** (`compute_price_signal()`) — free, no LLM. Checks *both* 1-day and 5-day `change_pct` against `settings.price_move_threshold_pct` (default 5%, either direction, configurable so the pipeline can be tested without waiting for real volatility) — catches a slow multi-day bleed that no single day would cross the threshold for, not just a sharp move. Crossing the threshold gates the expensive news step ("investigation trigger") for most holdings.
  - Emits `direction` (today's risk direction) and `trend` (the 5-day picture) as **separate fields**, not one value doing both jobs — e.g. a stock down 1.3% today inside a 5-day run that's still up 2% reports `direction=negative, trend=positive`, so the alert can say "today's move is negative, but the 5-day trend remains positive" instead of collapsing that nuance. `direction` follows today's move when horizons disagree; `trend` is always the 5-day sign.
- **News signal** (`news_service.classify_news_signal()`) — LLM-classified `direction`/`materiality`/`confidence`/`event_type`, both positive and negative (unlike `classify_holding_news`, which only flags downside for the dashboard News card — kept as a separate function so that already-working path is untouched). Computed when the price signal fires, **and always** for the user's top `NEWS_ALWAYS_CHECK_TOP_N` (5) holdings by portfolio weight regardless of price movement — bad news on a large position can break before the price reacts (e.g. announced after market close or over a weekend), so the position that matters most shouldn't wait for a price crash to get investigated. Bounded to keep LLM calls predictable.
- **Benchmark context** (`benchmark_service.get_benchmark_context()`) — moderates the fused signal via `signal_service.apply_context()` rather than adding a third parallel signal: NIFTY 50 always, plus a small static `industry → NSE index` mapping (keyed on yfinance's granular `industry` field, e.g. "Banks - Regional", **not** the broad `sector` field, which lumps banks/NBFCs/depositories together under "Financial Services"). Falls back to NIFTY FINANCIAL SERVICES for industries with no dedicated index, and to market-only when no mapping exists at all. A move mostly explained by the market/sector (`market_context="broad_based"`) gets downgraded one severity tier and annotated as such — the goal is flagging company-specific risk, not "the market had a red day."
- **Portfolio weight** — a holding ≥15% of the portfolio (`LARGE_POSITION_THRESHOLD_PCT`) gets escalated one severity tier; the same % move matters more in a large position than a small one.
- **Confidence fusion uses `min()`, not `mean()`** — price signal confidence is always a constant `1.0` (certainty the *number* is accurate, not a real probability), so averaging it with news' genuinely-uncertain LLM confidence always inflates the blend upward (e.g. `mean(1.0, 0.65) = 0.825` would clear an 0.8 gate the weak news evidence shouldn't). The weakest signal sets the ceiling.
Only two severity tiers are used throughout (`medium`/`high` internally, mapping to `significant`/`critical` on the `Alert` row) — matching every other `alert_type` in this codebase, no new tier for the frontend to not know how to style.
Alerts are `alert_type="market_event"`, cooldown is **per-instrument** (a fix from the original `_check_cooldown`, which filtered by `alert_type` only — one stock's alert would have silently suppressed every other stock's alert of the same type). `POST /api/alerts/refresh-signals` runs the same check on demand (dashboard's Recent Alerts refresh button).
Not built yet: **D** (fundamentals — no data source in this codebase at all yet), peer-basket benchmarks for industries with no clean NSE index (falls back to NIFTY FINANCIAL SERVICES / market-only instead), 20-day/volume/52-week-high anomaly detection, portfolio-weight-adjusted *trigger* thresholds (weight currently only escalates severity post-hoc, not the gate itself), and investment-thesis tracking.

**Phase 3 — recommendation routing** (`services/opportunity_service.py`): signals that clear a *meaningfully higher* bar than the plain informational alert (`is_opportunity_worthy()`: `market_context=="company_specific"` AND `severity=="high"` AND `confidence>=OPPORTUNITY_MIN_CONFIDENCE` (0.8) AND clean `direction` — "mixed" is explicitly excluded) get routed through `RECOMMENDATION` (a proposal scoped to the one flagged holding only — never suggests a different stock, unlike the chat pipeline's portfolio-wide `recommendation_node`) then `DEVIL_ADVOCATE` (critiques the proposal's evidence — dimensions are `priced_in`/`temporary_vs_structural`/`company_vs_sector`/`position_size`/`thesis_impact`/`alternative_action`, deliberately different from `devil_advocate.py`'s portfolio-reallocation-oriented dimensions, since challenging a single-stock signal-driven trade is a different question). A `proposal.action=="hold"` verdict from the LLM suppresses the alert entirely — the model has final veto power regardless of how the quantitative gates scored. Produces a **second, additive** `alert_type="signal_opportunity"` alongside the always-fired `market_event` alert (detection and decision stay separate); severity/messaging is templated deterministically from `critique.overall`, not another LLM call.

**News highlights:** `services/news_service.py` classifies stock-holding news impact (via `NEWS_INTELLIGENCE`) and persists critical/significant items to the `news_highlights` table. Stock holdings only for now (mutual funds/FDs/PPF/NPS have no per-instrument news feed). Deliberately **not** on a cron — `POST /api/news/refresh` recomputes on demand (dashboard's refresh button) and replaces the user's prior highlights; `GET /api/news` just reads what's stored. `select_top_movers()` ranks holdings by absolute day change (via the cheap, cached `get_stock_price`) and caps classification to the top 5 movers — this keeps LLM calls within Gemini's free-tier RPM limit and avoids spending a classification call on a stock that barely moved. Shares its classification logic (`classify_holding_news()`) and mover selection with `agents/news_intelligence.py`, used in-memory by the chat pipeline's `news_query` intent.

**News sources** (`services/news_providers/`, `BaseNewsProvider` interface): `GoogleNewsRSSProvider` is primary — an unofficial, undocumented Google endpoint (no public Google News API exists), chosen because it aggregates across Indian publications and had far better NSE small/midcap coverage in testing than yfinance's per-ticker feed or a financial-data vendor's ticker mapping. Being unofficial, it could change format or start rate-limiting without notice, so `FallbackNewsProvider` falls through to `YFinanceNewsProvider` (wraps `market_service.get_stock_news`, which has its own 7-day recency filter) whenever the primary returns nothing — including simply having no coverage for a stock, not just on errors. Queries use `market_service.get_company_name()` (resolves via `yf.Ticker().info`, cached 30 days) rather than the raw ticker/`display_name` — a bare ticker like "GILLETTE" returns razor-brand and concert news instead of Gillette India.

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
| `/dashboard` | Portfolio metrics, 1Y area chart, allocation donut, recent alerts, news highlights (manual refresh), quick-ask |
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
- **LLM calls:** Never import provider SDKs (anthropic, google.generativeai) directly in agent files. Always use `from llm import AGENT_ROLE` and call `await AGENT_ROLE.generate(prompt)` or `await AGENT_ROLE.generate_json(prompt)`.

## Environment variables

Backend `backend/.env`:
- `DATABASE_URL` — must use `postgresql+asyncpg://` scheme
- `REDIS_URL` — `redis://localhost:6379`
- `GOOGLE_AI_API_KEY` — from aistudio.google.com (free). Used by GeminiProvider (all agent roles) and GeminiEmbeddingProvider (agent memory), in every environment
- `ANTHROPIC_API_KEY` — optional, only needed if swapping an agent to Claude in registry.py
- `GROQ_API_KEY` — optional, free tier at console.groq.com. When set, `_auto()` in `llm/registry.py` wraps every Gemini agent in a `FallbackLLMProvider` that retries against Groq's `openai/gpt-oss-120b` if the primary call fails (rate limit, overload, outage). Unset by default — no key, no wrapping.
- `JWT_SECRET` — any random string for local dev
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — for Google OAuth backend token verification
- `ENVIRONMENT` — `"development"` (local) or `"production"` (Cloud Run)
- `QDRANT_URL`, `QDRANT_API_KEY` — local Docker instance by default (`http://localhost:6333`, no API key); agents degrade gracefully if unreachable
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
- Production uses the same `GOOGLE_AI_API_KEY`/AI Studio path as local dev — there is no Vertex AI provider
- GCP infra (Cloud SQL, Memorystore, Secret Manager) is not needed for local development
