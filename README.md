# পুঁজি (Punji) — Personal Finance Agent for Indian Investors

Punji is an autonomous personal finance agent built for Indian retail investors. It consolidates mutual funds, stocks, fixed deposits, PPF, and NPS into a single dashboard, computes XIRR and CAGR, runs Monte Carlo goal projections, and uses an LLM multi-agent pipeline to answer questions, detect concentration risk, monitor holdings for risk/opportunity signals, and send proactive alerts.

### Engineering highlights

- **Provider-agnostic LLM layer** — every agent role is a `BaseLLMProvider` swapped in from one registry file (Strategy + Registry pattern), with automatic **retry-with-backoff** on transient errors and a **cross-provider fallback** (Gemini → Groq) so a quota/rate-limit hit on one provider doesn't take an agent down. The retry policy is itself quota-aware: a *daily* quota exhaustion (no amount of backoff fixes that within the hour) skips straight to the fallback instead of wasting ~7s retrying a call that can't succeed until tomorrow.
- **Detection and decision, deliberately separate** — the signal engine always fires an informational alert when something unusual happens; only signals that clear a *meaningfully stricter* bar (company-specific, high severity and confidence, unambiguous direction) get escalated into an actual buy/sell recommendation. A raw "stock fell 5%" never reaches an LLM and becomes "sell" directly — it passes through five independent gates first, and the LLM itself has final veto power (a "hold" verdict suppresses the recommendation alert entirely, regardless of how the quantitative gates scored).
- **Recommendation, then adversarial critique** — every recommendation is generated scoped to the one flagged holding (never "sell X, consider Y instead" for an unrelated stock), then challenged by a devil's-advocate pass built specifically for single-stock signal trades (is this priced in? temporary or structural? does position size justify acting? is there a less aggressive alternative?) — not the generic portfolio-rebalancing critique reused wholesale from the chat pipeline.
- **Confidence fusion uses `min()`, not `mean()`** — a deterministic price signal always reports 1.0 confidence (it's certainty the *number* is accurate, not a real probability); averaging that with a genuinely-uncertain LLM-rated news confidence silently inflates weak evidence above the actionability threshold. The weakest signal sets the ceiling, not the strongest.
- **Benchmark-aware anomaly detection** — distinguishes a company-specific price move from a broad market/sector one, using an industry-mapped NSE index lookup (not just NIFTY 50) built on yfinance's granular `industry` field rather than its too-coarse `sector` field (which lumps banks, NBFCs, and depositories together under "Financial Services"). A move that's "just the market having a red day" is downgraded and annotated instead of alerting at full severity.
- **Multi-source data pipelines with quality-ranked fallback** — news comes from an unofficial-but-far-better-coverage Google News RSS source first, falling back to yfinance only when it finds nothing; the same fallback pattern used for LLM providers, applied again for a different resource.
- **Direction vs. trend, kept separate** — a stock down today inside an otherwise-positive 5-day run reports `direction=negative, trend=positive` rather than collapsing that nuance into one field, so alert text can say "today's dip, but the week is still up" instead of guessing wrong in either direction.

---

## Screenshots

### Dashboard

![Dashboard overview](docs/screenshots/dashboard-overview.png)

Portfolio Overview: total value, invested amount, unrealised P&L, and portfolio XIRR at a glance, a 1-year performance chart, and an asset-allocation donut broken down by equity/debt/gold/cash/real estate/alternative.

![Dashboard — Recent Alerts and News](docs/screenshots/dashboard-alerts-news.png)

Further down: the **Recent Alerts** card (with a manual refresh button that triggers the signal engine on demand) showing severity-badged, emoji-coded market-event alerts; the **News** card (Google News RSS-sourced, per-holding, with direct source links); and **Quick Actions** for common tasks.

### Holdings

![Holdings page](docs/screenshots/holdings.png)

Tab-filtered by instrument type (Mutual Fund shown here, with Stock/FD/PPF/NPS alongside), summary stat cards, and a sortable table with expandable rows, per-holding refresh, and CSV import.

### Alerts

![Alert detail view](docs/screenshots/alerts-detail.png)

An expanded `market_event` alert, showing the full evidence readout the signal engine stores: 1-day move, 5-day trend, performance relative to NIFTY 50 and the holding's industry index, portfolio weight, model confidence, and a plain-English assessment ("Broad market/sector move" here — CDSL's dividend news read as broadly positive by the LLM, but the price move itself tracked the wider market rather than being company-specific). The raw evidence trail, source article link, and thumbs up/down feedback are all visible without leaving the inbox.

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

### Proactive Portfolio Monitoring (Signal Engine)

A three-layer pipeline, not a single "price dropped → LLM → sell" shortcut:

**Layer 1 — Detection (`services/signal_service.py`, always fires an informational alert):**
- **Multi-signal fusion** — a free, deterministic **price signal** (1-day *and* 5-day change, catching both a sharp move and a slow multi-day bleed) combined with an LLM-classified **news signal** (direction, materiality, confidence, event type — both positive *and* negative, not just downside risk)
- **Benchmark-aware** — every flagged move is compared against NIFTY 50 and an industry-specific NSE index (Banks, Auto, Pharma, FMCG, IT, etc.), so a move that's really "the whole sector moved" gets downgraded and annotated instead of alerting at full severity as if it were company-specific
- **Portfolio-weighted severity** — the same % move is escalated for a position that's 20% of your portfolio and left alone for one that's 2%
- **Direction vs. trend** — separately reports today's risk direction and the broader 5-day trend, so a one-day dip inside an otherwise-positive week isn't misreported either way
- **Cost-bounded by design** — cheap price checks gate the expensive LLM step; only genuinely anomalous holdings (plus the top 5 by portfolio weight, checked every cycle regardless of price movement, since bad news on a large position can break before the price reacts) ever reach the LLM

**Layer 2 — Recommendation (`services/opportunity_service.py`, only for signals clearing a much stricter bar):**
- A signal is only "opportunity-worthy" if it's **company-specific** (not explained by the sector/market), **high severity**, **confidence ≥ 0.8**, and has a **clean direction** (conflicting price-vs-news signals are explicitly excluded — no forced choice on ambiguous evidence)
- The recommendation agent proposes a concrete action (buy/sell/trim/hold) scoped to *only* the flagged holding, with a rupee amount, timeline, and tax note
- A **devil's-advocate pass**, purpose-built for single-stock signal trades, then challenges the proposal's evidence: is this already priced in? temporary or structural? does the position size justify acting? is there a less aggressive alternative (monitor, partial trim, stop-loss)?
- If the recommendation agent itself concludes "hold," nothing gets surfaced — the LLM has final veto power over the quantitative gates

**Runs automatically** every ~2-3 hours during NSE market hours, plus an on-demand refresh from the dashboard.

### News Intelligence
- **Per-holding news classification** — recent news for each stock, filtered to a 7-day recency window and classified by impact (critical/significant/monitor/noise) via LLM
- **Google News RSS-powered** — chosen over financial-data-vendor news APIs after testing showed far better coverage of NSE small/midcaps (thinly covered by yfinance and typical aggregators), with automatic fallback if the primary source finds nothing
- **Disambiguated queries** — resolves a bare ticker to its full company name before searching (a raw ticker like "GILLETTE" returns razor-brand and concert news; "Gillette India Limited" doesn't)
- **Dashboard News card** — top-mover-prioritized highlights with direct article links, refreshable on demand

### Goal Planning
- **Multiple goals** — Retirement, house, education, etc. with separate target amounts and dates
- **SIP allocation** — Allocate monthly SIP amounts towards specific goals
- **Monte Carlo projections** — Weekly re-simulation using equity/debt allocation and historical volatility
- **Scenarios** — What-if analysis with P10/P50/P90 outcomes

### Alerts
- **Two independent alert cycles** — daily portfolio-level checks (rebalancing drift, FD maturity, goal risk, concentration) at 8 AM IST, plus the signal engine's intraday checks every ~2-3 hours during market hours
- **Two alert types from the signal engine** — informational `market_event` (always fires — price/news evidence, benchmark comparison, portfolio weight) and, only for the rare high-conviction case, a distinct `signal_opportunity` alert carrying a concrete proposal *and* its devil's-advocate critique side by side
- **Severity tiers** — Significant / critical, with per-instrument cooldowns so one stock's alert can't suppress another's
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
| AI | Gemini (`gemini-flash-latest` via AI Studio, `google-genai` SDK) for every agent, with automatic fallback to Groq (`openai/gpt-oss-120b`) on quota/overload; `text-embedding-004` (agent memory); GPT-4o-mini (MF composition) |
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
GROQ_API_KEY=               # free tier at console.groq.com — enables automatic fallback when Gemini errors
PRICE_MOVE_THRESHOLD_PCT=5.0 # signal engine's price-move trigger threshold, either direction
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

### News (`/dashboard`)

The dashboard's News card shows recent, classified news for your stock holdings, prioritized by day-mover ranking. Click refresh to re-fetch — it re-runs the classification for your top 5 movers and replaces the prior highlights. Each headline links directly to the source article.

Recency matters here: articles older than 7 days are filtered out before classification, so a months-old headline never gets surfaced as if it just happened.

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

Two independent alert cycles feed this inbox:

**Daily (8 AM IST)** — portfolio-level checks: rebalancing drift, FD maturity reminders, goal-at-risk warnings (Monte Carlo success probability trending down), and single-stock concentration.

**Intraday (every ~2-3 hours during market hours, plus an on-demand refresh from the dashboard)** — the signal engine's market-event alerts:
1. **Price signal** — 1-day and 5-day change checked against a configurable threshold (default 5%, either direction). Catches a slow bleed, not just a single sharp move.
2. **News signal** — for any holding whose price signal fires, *and always* for your top 5 holdings by portfolio weight regardless of price movement (bad news on a large position can break before the price reacts). An LLM classifies direction, materiality, and event type.
3. **Benchmark check** — the move is compared against NIFTY 50 and, where a clean NSE sector index exists for the holding's industry, that index too. A move mostly explained by the market/sector gets downgraded and the alert says so explicitly, rather than reading as company-specific risk when it isn't.
4. **Portfolio weight** — a large position's alert is escalated even if the raw % move looks moderate.

Each alert's reasoning (the actual evidence — price moves, benchmark deltas, news headline, portfolio weight) is stored and visible, not just a final verdict — you can see *why* something was flagged, not just that it was.

**When a signal is strong enough, you also get a recommendation, not just a flag.** A real example from testing — Tata Motors PV (TMPV) reported a 79% Q1 profit decline:

```
Signal:  -1.5% today, -4.4% over 5 days, underperforming both NIFTY 50 (+0.3%)
         and the Auto index (+0.9%) — a genuine company-specific move, not
         sector-wide. News confidence 0.95.

Proposal:  SELL — ₹8,714, immediate
Reasoning: "Q1 profit plunged 79%, causing a 6% share fall and a brokerage
           downgrade forecasting an 11% downside. Underperformance vs. both
           NIFTY and the Auto index confirms this is a company-specific
           earnings shock, not market noise."

Devil's advocate (moderate concern):
"Selling now may lock in a loss if the stock rebounds after the earnings
shock. Holding with a stop-loss could achieve similar risk reduction with
less finality."
```

Both the proposal and the critique are shown together — Punji doesn't just say "sell," it shows you the case *against* selling too, and leaves the decision to you. This only fires for the rare case that clears a much stricter bar than the informational alert (company-specific, high confidence, unambiguous direction); most flagged moves stay informational only.

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
| `POST` | `/api/alerts/refresh-signals` | Run the price+news+benchmark signal check now |
| `GET` | `/api/news` | List news highlights for your stock holdings |
| `POST` | `/api/news/refresh` | Re-fetch and re-classify news for your top movers |

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
│   │   ├── embeddings/  # Embedding provider for agent memory (Gemini text-embedding-004)
│   │   ├── fallback.py  # Cross-provider fallback (e.g. Gemini -> Groq on error)
│   │   └── retry.py     # Retry-with-backoff for transient provider errors
│   ├── migrations/      # Alembic migration versions
│   ├── models/          # SQLAlchemy ORM models
│   ├── routers/         # FastAPI route handlers
│   ├── scheduler/       # APScheduler cron jobs
│   └── services/        # Business logic
│       ├── benchmark_service.py     # NIFTY 50 + industry-index comparison
│       ├── composition_service.py   # MF portfolio composition (LLM-powered)
│       ├── concentration_service.py # Concentration risk detection
│       ├── exposure_service.py      # Portfolio look-through computation
│       ├── market_service.py        # NAV + stock price fetching + caching
│       ├── news_providers/          # Google News RSS (primary) + yfinance (fallback)
│       ├── news_service.py          # News classification (dashboard + signal engine)
│       ├── opportunity_service.py   # Phase 3 — recommendation + devil's-advocate critique
│       ├── portfolio_service.py     # XIRR, allocation, Monte Carlo
│       └── signal_service.py        # Price+news+benchmark signal fusion
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
