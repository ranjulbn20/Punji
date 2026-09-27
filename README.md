# পুঁজি (Punji) — Personal Finance Agent for Indian Investors

Punji is an autonomous personal finance agent built for Indian retail investors. It consolidates mutual funds, stocks, fixed deposits, PPF, and NPS into a single dashboard, computes XIRR and CAGR, runs Monte Carlo goal projections, and uses an LLM multi-agent pipeline to answer questions, detect concentration risk, and send proactive alerts.

---

## Features

### Portfolio Tracking
- **Multi-instrument support** — Mutual funds (direct/regular), stocks (NSE/BSE), fixed deposits, PPF, NPS
- **Real-time prices** — MF NAVs via AMFI, stock prices via yfinance, cached in Redis
- **XIRR computation** — Extended IRR across all instruments, individually and for the whole portfolio
- **P&L tracking** — Unrealised gain/loss per holding with percentage and absolute values
- **Historical snapshots** — Daily portfolio value snapshots for performance charting

### Portfolio Look-Through (Exposure Analysis)
- **Company-level exposure** — See your total allocation to each company across direct stocks *and* the underlying holdings of your mutual funds combined
- **Sector-level exposure** — Consolidated sector breakdown (Financial Services, IT, FMCG, Auto, Pharma, etc.) across your entire portfolio including MF underlying stocks
- **Direct vs indirect split** — For each company and sector, the view distinguishes what you hold directly vs what you hold via MFs
- **MF composition via LLM** — Portfolio composition for each mutual fund is fetched via GPT-4o-mini (trained on AMFI monthly disclosures) and stored locally; refreshable on demand

### Import & CSV Parsing
- **Zerodha** — Holdings and P&L CSV exports
- **Groww** — Portfolio export CSV
- **CAMS CAS** — Consolidated Account Statement (PDF and CSV) with PDF password support
- **KFIN** — Statement of account CSV
- **Generic CSV** — Auto-detection from column headers

### AI Agent Pipeline
- **Natural language Q&A** — Ask questions about your portfolio in plain English ("What's my HDFC Bank total exposure including MFs?")
- **Concentration risk alerts** — Proactive detection of single-stock, sector, and business group concentration
- **Goal tracking** — Monte Carlo simulation for each financial goal with P10/P50/P90 success probability
- **Proactive alerts** — Morning digest at 8 AM IST with portfolio-specific insights
- **Chat interface** — Ask questions in plain English; the full answer is generated up front, then delivered over SSE with a simulated typing effect and a reasoning trace of which agents ran

### Goal Planning
- **Multiple goals** — Retirement, house, education, etc. with separate target amounts and dates
- **SIP allocation** — Allocate monthly SIP amounts towards specific goals
- **Monte Carlo projections** — Weekly re-simulation using equity/debt allocation and historical volatility
- **Scenarios** — What-if analysis with P10/P50/P90 outcomes

### Alerts
- **Severity tiers** — Info / warning / critical with colour-coded badges
- **Thumbs up/down feedback** — Rate alert quality to improve future alerts
- **Real-time push** — Alerts delivered via WebSocket connection

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind CSS v4, Recharts, Zustand |
| Backend | FastAPI (async), SQLAlchemy 2.0, Alembic, PostgreSQL 15 |
| Cache | Redis 7 |
| Vector store | Qdrant (agent memory embeddings) |
| AI | Gemini (flash-latest / 1.5-flash via AI Studio), text-embedding-004 (agent memory), GPT-4o-mini (composition) |
| Auth | NextAuth v5 (Google OAuth + email/password), JWT (HS256) |
| Infra | Docker Compose (local), Cloud Run (GCP) |

---

## Prerequisites

- Docker Desktop, OrbStack, or Colima (for Postgres + Redis + Qdrant)
- Node.js 20+ and npm
- Python 3.11

---

## Local Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd Punji
```

### 2. Backend environment

Copy and fill in `backend/.env`:

```bash
cp backend/.env.example backend/.env   # if example exists, otherwise create it
```

Required variables:

```env
# Database & cache
DATABASE_URL=postgresql+asyncpg://punji:punji@localhost:5432/punji
REDIS_URL=redis://localhost:6379

# LLM + agent memory embeddings — get free key at aistudio.google.com
GOOGLE_AI_API_KEY=your_google_ai_key

# Qdrant — local Docker instance started by docker-compose, no auth needed
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

# OpenAI — for MF portfolio composition look-through
OPENAI_API_KEY=sk-...

# Auth
JWT_SECRET=any_random_string_for_local_dev
GOOGLE_CLIENT_ID=your_oauth_client_id
GOOGLE_CLIENT_SECRET=your_oauth_client_secret

# Optional
ANTHROPIC_API_KEY=          # only if swapping an agent to Claude
NEWS_API_KEY=               # for news intelligence agent
RBI_REPO_RATE=6.5           # current RBI repo rate in percent

ENVIRONMENT=development
```

### 3. Frontend environment

```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=any_random_string
GOOGLE_CLIENT_ID=your_oauth_client_id
GOOGLE_CLIENT_SECRET=your_oauth_client_secret
```

### 4. Start everything

```bash
bash start.sh
```

This runs Docker infra (Postgres + Redis + Qdrant), applies DB migrations, starts the FastAPI backend on `:8000`, and the Next.js frontend on `:3000`.

Or start each piece individually:

```bash
docker-compose up -d                                         # infra
cd backend && .venv/bin/alembic upgrade head                 # migrations
cd backend && .venv/bin/uvicorn main:app --reload            # API
cd frontend && npm run dev                                   # UI
```

API docs: http://localhost:8000/docs

---

## User Guide

### Signing in

Open http://localhost:3000. Sign in with Google OAuth or register with email and password.

On first login you'll be taken through a 3-step onboarding:
1. **Risk profile** — Answer a question about your drawdown tolerance
2. **Goals** — Add your first financial goal (retirement, house, etc.)
3. **Import** — Upload your first broker CSV

---

### Importing your portfolio

Go to **Holdings → Import** and select your broker:

| Broker | File to export |
|---|---|
| Zerodha | Console → Portfolio → Holdings → Download CSV |
| Groww | Groww app → Profile → Portfolio → Download |
| CAMS | CAMS website → Statement → Consolidated (PDF or CSV) |
| KFIN | KFintech website → Statement of Account |

Drag and drop the file. For CAMS PDF statements, enter your PDF password when prompted. Review the preview and click **Confirm** to import.

---

### Portfolio Look-Through (`/exposure`)

This is the most unique feature. Indian MF investors often hold the same stock across multiple funds without realising it. The **Exposure** page shows your true consolidated position.

**What it shows:**
- **Sector chart** — Horizontal stacked bars showing how much of your portfolio is in each sector (teal = direct stocks, indigo = via MF underlying holdings)
- **Company list** — Every company you own, directly or through MFs, sorted by total exposure. Each row shows `total% = direct% + via MF%`
- **Expand a company row** — See exactly which direct holding or which MF contributes what percentage

**Refreshing MF composition:**

Click **Refresh MF data** to fetch the underlying portfolio of each of your mutual funds via GPT-4o-mini. The LLM is trained on AMFI monthly disclosures and returns the top 25 holdings per fund with ISINs, weights, and sector labels. Data is cached in the database and only re-fetched monthly.

> **Note:** LLM-sourced composition data reflects the model's training cutoff (~early 2025). It is accurate for most equity funds and stable enough for look-through analysis. AMFI publishes monthly disclosures on their website if you prefer to verify.

---

### Chat (`/chat`)

Ask natural language questions about your portfolio:

- *"What is my total HDFC Bank exposure including mutual funds?"*
- *"Am I too concentrated in IT?"*
- *"Which of my MFs have the most overlap?"*
- *"What is my portfolio XIRR?"*
- *"Am I on track for my retirement goal?"*

**How a message is handled:**

1. **Intent detection** — `ORCHESTRATOR` (Gemini) classifies the query into one of 9 intents (`portfolio_overview`, `portfolio_advice`, `rebalancing`, `goal_check`, `tax_query`, `stock_question`, `news_query`, `fd_advice`, `general_finance`).
2. **Agent routing** — the intent maps to an ordered pipeline of agent nodes. For example `portfolio_advice` runs `portfolio_analyser → market_intelligence → recommendation → devil_advocate → synthesise`; `goal_check` runs `goal_tracker → portfolio_analyser → respond`. Each node reads/writes a shared `PunjiState` (allocation, concentration, market context, goal analysis, a draft proposal, and a critique of that proposal).
3. **Memory** — before the pipeline runs, the query is embedded (Gemini `text-embedding-004`, via the same `EMBEDDING` provider entry in `llm/registry.py` used for all agent memory) and Qdrant is searched for the semantically nearest past exchanges with this user, filtered by `user_id`. If Qdrant is unreachable or unconfigured, this falls back to the most recent memories from Postgres instead of failing the request. After the pipeline finishes, a summary of the exchange is embedded and saved back to both stores — Postgres always, Qdrant best-effort.
4. **Synthesis** — the final node combines the proposal, the devil's-advocate critique, market context, goal state, and the retrieved memories into one answer via a single LLM call, always appended with a "not financial advice" disclaimer.
5. **Delivery** — the backend computes the *entire* answer before sending anything back. It then streams it to the frontend over SSE (`token` events) one character at a time to produce a typing effect, followed by a single `reasoning_trace` event (a flat list of one-line log entries, one per agent node that ran) and a `done` event. This is not token-by-token LLM streaming — the model call itself is not incremental.

Click the **Reasoning** accordion to see which agents ran and a short summary of what each contributed.

Qdrant runs locally via `docker-compose` (`punji_qdrant`, port `6333`) alongside Postgres and Redis, and is the durable index behind step 3 — Postgres remains the source of truth for every memory row, so the Qdrant collection can be dropped and rebuilt at any time by replaying saved memories.

---

### Goals (`/goals`)

Add financial goals with a target amount and target date. Punji runs Monte Carlo simulation weekly and shows your probability of reaching each goal (P10/P50/P90 confidence bands). Allocate monthly SIP amounts to specific goals.

---

### Scenarios (`/scenarios`)

Run what-if analysis:
- Change your monthly SIP amount
- Shift your asset allocation (more equity / more debt)
- Pick a preset scenario (aggressive growth, capital preservation, etc.)

The simulator shows how P10/P50/P90 outcomes shift for each goal.

---

### Alerts (`/alerts`)

Proactive alerts fire every morning at 8 AM IST and include:
- Concentration risk warnings (single stock > 10%, sector > 30%)
- Underperforming stocks (trailing sector by > 15% over 3 months)
- Goal drift warnings
- Market macro updates

Rate each alert with thumbs up/down to improve future alert relevance.

---

## Backend Commands

All run from `backend/` using the Python venv:

```bash
.venv/bin/uvicorn main:app --reload                          # Run dev server
.venv/bin/alembic upgrade head                               # Apply migrations
.venv/bin/alembic revision --autogenerate -m "description"   # New migration
.venv/bin/alembic downgrade -1                               # Rollback one
.venv/bin/python -c "import main; print('ok')"               # Smoke test
.venv/bin/pip install -r requirements.txt                    # Install deps
```

---

## API Reference

Interactive docs at http://localhost:8000/docs (Swagger UI).

Key endpoints:

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/portfolio/summary` | Total value, P&L, XIRR, allocation |
| `GET` | `/api/portfolio/exposure` | Look-through by company and sector |
| `POST` | `/api/portfolio/refresh-compositions` | Refresh MF underlying holdings via LLM |
| `GET` | `/api/portfolio/concentration` | Concentration risk with alert thresholds |
| `GET` | `/api/holdings` | List all holdings (filter by type) |
| `POST` | `/api/imports/upload` | Upload broker CSV/PDF |
| `POST` | `/api/agent/chat` | Streaming chat (SSE) |
| `GET` | `/api/goals` | List goals with Monte Carlo results |
| `GET` | `/api/alerts` | List alerts |

---

## GCP Deployment

```bash
gcloud builds submit --config cloudbuild.yaml
```

The Cloud Build pipeline builds the backend Docker image, pushes to Artifact Registry, and deploys to Cloud Run (`asia-south1`). The frontend can be deployed to Vercel or any static host. All Gemini calls (chat, agent memory embeddings) go through the same AI Studio API key (`GOOGLE_AI_API_KEY`) in every environment — there is no separate Vertex AI path.

---

## Project Structure

```
Punji/
├── backend/
│   ├── agents/          # LLM agent pipeline (orchestrator, recommendation, etc.)
│   ├── importers/       # CSV/PDF parsers (Zerodha, Groww, CAMS, KFIN)
│   ├── llm/             # Provider-agnostic LLM abstraction layer
│   │   ├── registry.py  # THE ONLY FILE to edit when swapping models
│   │   ├── providers/   # Gemini, Anthropic, Groq, OpenAI
│   │   └── embeddings/  # Embedding provider for agent memory (Gemini text-embedding-004)
│   ├── migrations/      # Alembic migration versions
│   ├── models/          # SQLAlchemy ORM models
│   ├── routers/         # FastAPI route handlers
│   ├── scheduler/       # APScheduler cron jobs
│   └── services/        # Business logic
│       ├── composition_service.py   # MF portfolio composition (LLM-powered)
│       ├── concentration_service.py # Concentration risk detection
│       ├── exposure_service.py      # Portfolio look-through computation
│       ├── market_service.py        # NAV + stock price fetching + caching
│       └── portfolio_service.py     # XIRR, allocation, Monte Carlo
└── frontend/
    ├── app/             # Next.js App Router pages
    │   ├── exposure/    # Portfolio look-through page
    │   ├── dashboard/
    │   ├── holdings/
    │   ├── goals/
    │   ├── chat/
    │   └── ...
    ├── components/
    └── lib/
        ├── api.ts       # Typed API client
        └── websocket.ts # Real-time alert WebSocket
```

---

## License

Private — all rights reserved.
