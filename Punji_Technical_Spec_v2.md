# Punji — Technical Specification v2.0

> Autonomous Personal Finance Agent  
> Name: পুঁজি (Punji) — Bengali for capital and investment corpus  
> Status: Pre-implementation review  
> Intended reader: Claude Code (VS Code) for implementation  
> Author: Ranjul Bandyopadhyay

---

## How to Use This Document

This document is the single source of truth for building Punji. It is written for Claude Code to implement from scratch. Every architectural decision is explained with its reasoning so the implementer understands *why*, not just *what*.

Read the entire document before writing any code. Implementation order follows Section 11 (Build Plan).

---

## Table of Contents

1. [Product Vision](#1-product-vision)
2. [Core Design Principles](#2-core-design-principles)
3. [System Architecture](#3-system-architecture)
4. [Technology Stack](#4-technology-stack)
5. [Database Schema](#5-database-schema)
6. [Agent Design](#6-agent-design)
7. [Holdings Import System](#7-holdings-import-system)
8. [Financial Mathematics Engine](#8-financial-mathematics-engine)
9. [API Specification](#9-api-specification)
10. [Frontend Specification](#10-frontend-specification)
11. [Week-by-Week Build Plan](#11-week-by-week-build-plan)
12. [Deployment](#12-deployment)
13. [Cost Reference](#13-cost-reference)

---

## 1. Product Vision

### What Punji Is

Punji is an autonomous personal finance agent that monitors your entire investment portfolio — mutual funds, stocks, fixed deposits, PPF, NPS, and any future instrument — and proactively tells you what needs attention, why, and what to do about it. It reasons about your full financial picture as a unified whole, not as siloed buckets.

### What Makes It Different From Existing Apps

Every existing personal finance app — INDmoney, Groww, Kuvera, Zerodha Coin — is a dashboard. They show you numbers. They wait for you to open them.

Punji is an agent. It comes to you. It reasons. It explains.

| Capability | INDmoney / Groww | Punji |
|---|---|---|
| Portfolio tracking | Yes | Yes |
| Returns calculation | Absolute % (misleading) | XIRR (accurate) |
| FDs in unified allocation | Partial | Yes — treated as debt instruments |
| Proactive alerts | Push notifications (rule-based) | Agent-driven, signal-scored, noise-filtered |
| Rebalancing suggestions | Generic nudges | Specific, with reasoning + devil's advocate critique |
| Goal tracking | Simple linear projection | Monte Carlo simulation (optional feature) |
| Stock concentration risk | No | Yes — single stock, sector, group exposure |
| Adverse news monitoring | No | Yes — LLM-classified news per holding |
| Fund overlap detection | No | Yes — identifies hidden concentration across funds |
| Cross-instrument exposure | No | Yes — computes real company/group exposure across stocks + MF holdings + FDs |
| Explanation of suggestions | None | Full reasoning trace visible to user |
| Memory across sessions | Stateless | Persists and evolves user model over time |

### Non-Goals

- Does not predict stock prices or market direction
- Does not place trades on behalf of users
- Does not provide SEBI-regulated investment advice — all suggestions carry "not financial advice" framing
- Does not require goals to be configured — goals are an optional layer

---

## 2. Core Design Principles

These principles govern every implementation decision. When in doubt, refer back here.

### Principle 1: Loose Coupling via Instrument Abstraction

The system must support any financial instrument — MF, stock, FD, PPF, NPS, Gold, Real Estate — without schema changes. This is achieved via a single unified `holdings` table with a JSONB `metadata` column for instrument-specific fields. Adding a new instrument means writing a new instrument handler class, not altering the database.

### Principle 2: Event-Driven, Not Request-Driven

The proactive alert system runs independently of user activity. A scheduler triggers agent runs. A Redis Streams message bus decouples producers (portfolio updates) from consumers (alert agent). The user experience is the app coming to the user, not the user polling the app.

### Principle 3: Agent Decisions Are Explainable

Every suggestion, alert, and recommendation carries a full reasoning trace. The user can always see why the agent said what it said. The reasoning trace is stored in state and returned with every agent response.

### Principle 4: Goals Are Optional

The core portfolio — holdings, allocation, alerts, XIRR, concentration risk, news — works with zero goals configured. Goals are an additive layer that activates only when the user creates one. Nothing in the core system depends on goals existing.

### Principle 5: Financial Mathematics Is Sacred

XIRR, not absolute returns. Monte Carlo simulation, not linear projection. Sharpe ratio and max drawdown for risk. Benchmark comparison for context. These are non-negotiable. Incorrect financial numbers destroy user trust permanently.

### Principle 6: Import Over Manual Entry

The biggest onboarding friction is manual data entry. The system prioritises CSV import from all major Indian platforms and the CAMS Consolidated Account Statement. Manual entry exists as fallback only. Live broker API connections are designed for but not implemented in v1.

---

## 3. System Architecture

### High-Level Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         USER LAYER                               │
│           Next.js 14 (App Router) + Tailwind CSS                 │
│    Dashboard | Chat | Alerts | Holdings | Goals | Scenarios      │
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTPS / WebSocket (WSS)
┌────────────────────────────▼─────────────────────────────────────┐
│                        API GATEWAY                               │
│                    FastAPI (Python 3.11)                         │
│           JWT Auth | Rate Limiting | CORS | Input Validation     │
└──────────┬──────────────────────────────────────┬────────────────┘
           │                                      │
┌──────────▼──────────────┐          ┌────────────▼───────────────┐
│    Portfolio Service    │          │    Agent Orchestrator       │
│    (Pure Python)        │          │    (LangGraph)              │
│                         │          │                             │
│  XIRR Calculator        │          │  Intent Detection           │
│  Allocation Engine      │          │  Task Decomposition         │
│  Concentration Detector │          │  Agent Routing              │
│  Benchmark Comparator   │          │  State Management           │
│  Risk Metrics           │          │  Conflict Resolution        │
│  Import Service         │          │  Memory Read/Write          │
└──────────┬──────────────┘          └────────────┬───────────────┘
           │                                      │
           └──────────────────┬───────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────────┐
│                       MESSAGE BUS                                │
│                     Redis Streams                                │
│                                                                  │
│  portfolio.updated | market.data.refreshed | alert.triggered    │
│  goal.recalculated | agent.memory.updated | import.completed    │
└───────┬──────────────────────────────────────────────┬───────────┘
        │                                              │
┌───────▼──────────────┐                  ┌───────────▼───────────┐
│   Scheduler Service  │                  │  Notification Service  │
│   (APScheduler)      │                  │  (WebSocket + Email)   │
│                      │                  │                        │
│  Daily agent runs    │                  │  Real-time alerts      │
│  Market data refresh │                  │  Weekly digest email   │
│  Portfolio snapshots │                  │  In-app notifications  │
│  Monte Carlo weekly  │                  │                        │
│  News monitoring     │                  │                        │
└──────────────────────┘                  └────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────────┐
│                         DATA LAYER                               │
│                                                                  │
│  PostgreSQL 15          Redis 7           Qdrant Cloud           │
│  Primary database       Cache + streams   Vector database        │
│  All relational data    NAV cache         Agent memory           │
│  Transaction history    Sessions          Semantic search        │
│  Snapshots              Rate limits       Past suggestions       │
└──────────────────────────────────────────────────────────────────┘
```

### Request Flow: Conversational Query

```
User: "Should I rebalance my portfolio this month?"
  │
  ▼
FastAPI validates JWT, extracts user_id
  │
  ▼
Orchestrator Agent initialises LangGraph state:
  - Loads risk profile from PostgreSQL
  - Fetches top-5 relevant memories from Qdrant (semantic search on query)
  - Detects intent: portfolio_advice
  - Decomposes into tasks
  │
  ├──► Portfolio Analyser Agent
  │      Fetches all holdings, computes current allocation %
  │      Identifies drift from target allocation
  │      Checks concentration risks
  │      Returns: allocation_report
  │
  ├──► Market Intelligence Agent
  │      Checks Redis cache for NAV data (4hr TTL)
  │      Fetches fresh data if stale
  │      Gets Nifty P/E, current interest rates, macro context
  │      Returns: market_context
  │
  ├──► Recommendation Agent (Claude Sonnet)
  │      Combines allocation_report + market_context + user memories
  │      Generates specific, actionable proposal with amounts
  │      Returns: proposal (structured JSON)
  │
  ├──► Devil's Advocate Agent (Gemini Flash)
  │      Receives proposal
  │      Finds strongest counterarguments
  │      Returns: critique (structured JSON with severity)
  │
  ▼
Orchestrator synthesises proposal + critique
Writes new observations to agent_memory + Qdrant
Streams response tokens to frontend via SSE
Returns full reasoning_trace with final response
```

### Request Flow: Proactive Alert (Scheduled)

```
APScheduler: daily 8:00 AM IST
  │
  ▼
Proactive Alert Agent runs for each active user:
  │
  ├── Compute allocation drift from target
  ├── Check all FD maturity dates
  ├── Check goal success probabilities (if user has goals)
  ├── Run news check for all stock/MF holdings
  ├── Check concentration thresholds
  ├── Check tax year proximity (Feb-March)
  │
  └── For each potential alert:
        Compute signal score (1-10)
        Check cooldown (was user notified recently?)
        Only alerts scoring >= 7 proceed
  │
  ▼
Qualifying alerts → Redis Streams → Notification Service
  → WebSocket push to connected clients
  → Stored in alerts table for inbox
```

### Folder Structure

```
punji/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # All environment variables
│   ├── database.py                # SQLAlchemy async engine + session
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── holding.py
│   │   ├── transaction.py
│   │   ├── goal.py
│   │   ├── alert.py
│   │   ├── agent_memory.py
│   │   └── portfolio_snapshot.py
│   ├── schemas/                   # Pydantic request/response models
│   │   ├── user.py
│   │   ├── holding.py
│   │   ├── transaction.py
│   │   ├── goal.py
│   │   └── agent.py
│   ├── routers/                   # FastAPI route handlers
│   │   ├── auth.py
│   │   ├── holdings.py
│   │   ├── transactions.py
│   │   ├── goals.py
│   │   ├── alerts.py
│   │   ├── agent.py
│   │   ├── market.py
│   │   ├── scenarios.py
│   │   └── imports.py
│   ├── services/                  # Business logic (no HTTP concerns)
│   │   ├── portfolio_service.py   # XIRR, allocation, risk metrics
│   │   ├── market_service.py      # NAV, stock prices, macro data
│   │   ├── import_service.py      # CSV parsing, format detection
│   │   ├── notification_service.py
│   │   └── snapshot_service.py
│   ├── agents/                    # All LangGraph agent definitions
│   │   ├── orchestrator.py
│   │   ├── portfolio_analyser.py
│   │   ├── market_intelligence.py
│   │   ├── goal_tracker.py
│   │   ├── recommendation.py
│   │   ├── devil_advocate.py
│   │   ├── proactive_alert.py
│   │   ├── news_intelligence.py
│   │   └── concentration_risk.py
│   ├── instruments/               # One handler per instrument type
│   │   ├── base.py                # Abstract InstrumentHandler
│   │   ├── mutual_fund.py
│   │   ├── stock.py
│   │   ├── fixed_deposit.py
│   │   ├── ppf.py                 # Stub — no value refresh logic yet
│   │   └── nps.py                 # Stub — no value refresh logic yet
│   ├── importers/                 # One parser per CSV format
│   │   ├── base.py                # Abstract CSVImporter
│   │   ├── zerodha.py
│   │   ├── groww.py
│   │   ├── kuvera.py
│   │   ├── cams_cas.py
│   │   └── generic.py             # Claude-powered fallback parser
│   ├── connectors/                # Future live broker connections
│   │   ├── base.py                # Abstract InstrumentConnector interface
│   │   └── zerodha_kite.py        # Stub only — not functional in v1
│   ├── scheduler/
│   │   └── jobs.py                # All APScheduler job definitions
│   └── migrations/                # Alembic migration files
│       └── versions/
├── frontend/
│   ├── app/                       # Next.js App Router
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   ├── (app)/
│   │   │   ├── layout.tsx
│   │   │   ├── dashboard/page.tsx
│   │   │   ├── holdings/page.tsx
│   │   │   ├── goals/page.tsx
│   │   │   ├── alerts/page.tsx
│   │   │   ├── chat/page.tsx
│   │   │   ├── scenarios/page.tsx
│   │   │   └── settings/page.tsx
│   │   └── onboarding/page.tsx
│   ├── components/
│   │   ├── portfolio/
│   │   ├── charts/
│   │   ├── chat/
│   │   ├── alerts/
│   │   └── ui/
│   ├── lib/
│   │   ├── api.ts
│   │   └── websocket.ts
│   └── store/
│       └── index.ts               # Zustand store
└── docker-compose.yml             # Local development (postgres + redis)
```

---

## 4. Technology Stack

### Backend

| Component | Technology | Reason |
|---|---|---|
| Language | Python 3.11 | LangGraph ecosystem, scipy/numpy for financial math |
| API Framework | FastAPI 0.111+ | Async-native, automatic OpenAPI docs, type safety via Pydantic |
| Agent Orchestration | LangGraph (latest) | State machines for multi-agent coordination |
| LLM — Conversational | Claude Sonnet (claude-sonnet-4-20250514) | Best reasoning quality for financial suggestions |
| LLM — Background | Gemini 1.5 Flash | ~10x cheaper; used for Devil's Advocate, Alert Agent, News Agent |
| ORM | SQLAlchemy 2.0 async | Type-safe async database access |
| Migrations | Alembic | Schema version control |
| Auth | python-jose + passlib | JWT tokens + bcrypt password hashing |
| Google OAuth | authlib | Google OAuth 2.0 flow |
| Scheduler | APScheduler 3.x | Async-compatible cron and interval jobs |
| HTTP Client | httpx | Async HTTP for external API calls |
| Financial Math | scipy + numpy | XIRR (brentq solver), Monte Carlo, risk metrics |
| Market Data | yfinance | Stock prices, benchmark indices, company news |
| PDF Parsing | pdfplumber | CAMS CAS PDF statement parsing |
| Testing | pytest + pytest-asyncio | Async test support |

### Data Layer

| Store | Technology | Purpose |
|---|---|---|
| Primary Database | PostgreSQL 15 | All relational data |
| Cache + Message Bus | Redis 7 | NAV cache (4hr TTL), sessions, Redis Streams for events |
| Vector Database | Qdrant Cloud (free tier) | Agent memory embeddings, semantic search |

### Frontend

| Component | Technology | Reason |
|---|---|---|
| Framework | Next.js 14 App Router | SSR, file-based routing, API routes |
| Styling | Tailwind CSS 3.x + CSS Variables | Utility-first with design token system for theming |
| Component Library | shadcn/ui | Unstyled, accessible, fully customisable — production grade |
| Charts | Recharts | React-native, composable, themeable |
| State | Zustand | Lightweight, async-friendly |
| Auth | NextAuth.js | Handles Google OAuth + JWT session management |
| Forms | react-hook-form + zod | Performant forms with schema validation |
| Notifications | react-hot-toast | Toast alerts |
| Animations | Framer Motion | Page transitions, micro-interactions |
| Icons | Lucide React | Consistent, clean icon set |
| Theme | next-themes | Dark/light mode with system preference detection, no flash |
| Fonts | Inter (body) + Cal Sans (headings) | Professional, legible at all sizes |

### External Data Sources (All Free)

| Data | Source | Notes |
|---|---|---|
| MF NAV — India | MFAPI.in | `https://api.mfapi.in/mf/{scheme_code}` — free, no key needed |
| MF NAV Historical | MFAPI.in | Full NAV history per scheme |
| Stock Prices | yfinance (Yahoo Finance) | Rate limited — cache aggressively in Redis |
| Nifty P/E + macro | NSE India / yfinance | Nifty50 = `^NSEI` in yfinance |
| Company News | yfinance `.news` | Per-ticker news, completely free |
| Company News (backup) | NewsAPI.org | Free tier: 100 requests/day |
| FD Interest Rates | Seeded manually in DB | Admin updates weekly |
| CAMS CAS | User uploads | Richest MF data source — covers all platforms |

---

## 5. Database Schema

### Design Decisions

**Single unified holdings table:** All instrument types in one table. `instrument_type` identifies the instrument. `asset_class` drives all allocation calculations. `metadata` JSONB holds instrument-specific fields. Adding PPF, NPS, Gold, or any future instrument requires zero schema changes — only a new instrument handler class.

**Transactions table is the source of truth for XIRR:** Every cashflow — buy, sell, SIP, FD deposit, maturity — lives here. XIRR is computed from this table, not stored as a static field on the holding.

**Goals are optional:** No core table has a non-nullable foreign key to goals. The `goal_id` on holdings is nullable. Goal features activate conditionally.

**Agent memory in two places:** Structured observations in PostgreSQL for querying and management; vector embeddings in Qdrant for semantic similarity search. Both are maintained in sync.

### Full Schema

```sql
-- ============================================================
-- USERS AND AUTHENTICATION
-- ============================================================

CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email               VARCHAR(255) UNIQUE NOT NULL,
    full_name           VARCHAR(255),
    profile_picture_url VARCHAR(500),

    -- Auth: both nullable — user may use Google only or email only
    password_hash       VARCHAR(255),
    google_user_id      VARCHAR(255) UNIQUE,
    auth_provider       VARCHAR(20) DEFAULT 'email',
    -- Values: 'email' | 'google' | 'both'

    -- Onboarding progress tracking
    onboarding_step     INTEGER DEFAULT 0,
    -- 0: registered, no data
    -- 1: at least one holding added
    -- 2: risk profile completed
    -- 3: fully onboarded (goals not required)

    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- RISK PROFILE
-- Created via single onboarding question.
-- Refined over time through agent conversations.
-- ============================================================

CREATE TABLE risk_profiles (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,

    -- Single question answer from onboarding
    drawdown_response       VARCHAR(20) NOT NULL,
    -- Values: 'sell_everything' | 'hold' | 'buy_more'

    -- Derived from drawdown_response
    risk_score              INTEGER CHECK (risk_score BETWEEN 1 AND 10),
    risk_category           VARCHAR(20),
    -- Values: 'conservative' | 'moderate' | 'aggressive'

    -- Target allocation percentages — basis for drift detection alerts
    target_equity_pct       DECIMAL(5,2),
    target_debt_pct         DECIMAL(5,2),
    target_gold_pct         DECIMAL(5,2),
    target_cash_pct         DECIMAL(5,2),

    -- Additional context gathered through agent conversations
    -- Updated incrementally as agent learns more about user
    additional_context      JSONB DEFAULT '{}',
    -- Example: {"monthly_income": 150000, "monthly_expenses": 80000,
    --            "investment_horizon_years": 15, "emergency_fund_months": 6}

    last_reviewed_at        TIMESTAMPTZ,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- UNIFIED HOLDINGS TABLE
-- One row per investment holding, any instrument type.
-- instrument_type: what is it
-- asset_class: how it factors into allocation
-- metadata: all instrument-specific fields (flexible JSONB)
-- ============================================================

CREATE TABLE holdings (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES users(id) ON DELETE CASCADE,

    instrument_type     VARCHAR(50) NOT NULL,
    -- Values: 'mutual_fund' | 'stock' | 'fixed_deposit' | 'ppf' |
    --         'nps' | 'gold_sgb' | 'gold_etf' | 'real_estate' | 'crypto'

    display_name        VARCHAR(500) NOT NULL,
    -- Human-readable name shown in UI
    -- Examples: "Parag Parikh Flexi Cap Fund"
    --           "Reliance Industries Ltd"
    --           "SBI Fixed Deposit 7.1% — Mar 2026"

    asset_class         VARCHAR(20) NOT NULL,
    -- Values: 'equity' | 'debt' | 'gold' | 'real_estate' | 'cash' | 'alternative'
    -- FDs are 'debt'. PPF is 'debt'. NPS equity portion is 'equity'.

    -- Universal financial fields — every instrument has these
    invested_amount     BIGINT NOT NULL DEFAULT 0,   -- INR
    current_value       BIGINT NOT NULL DEFAULT 0,   -- INR, updated by instrument handler
    unrealised_pnl      BIGINT GENERATED ALWAYS AS (current_value - invested_amount) STORED,
    xirr                DECIMAL(6,2),                -- computed from transactions, nullable

    -- Optional goal linkage
    goal_id             UUID REFERENCES goals(id) ON DELETE SET NULL,

    -- Instrument-specific fields
    metadata            JSONB NOT NULL DEFAULT '{}',
    -- See Section 5a for metadata structure per instrument type

    is_active           BOOLEAN DEFAULT TRUE,        -- soft delete
    last_refreshed_at   TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_holdings_user_id ON holdings(user_id);
CREATE INDEX idx_holdings_user_active ON holdings(user_id, is_active);
CREATE INDEX idx_holdings_instrument_type ON holdings(instrument_type);
CREATE INDEX idx_holdings_asset_class ON holdings(asset_class);
CREATE INDEX idx_holdings_metadata ON holdings USING GIN(metadata);
-- GIN index enables: WHERE metadata->>'scheme_code' = '120503'
--                    WHERE metadata @> '{"is_sip": true}'

-- ============================================================
-- TRANSACTIONS
-- Source of truth for XIRR calculation.
-- Every cashflow for every instrument lives here.
-- ============================================================

CREATE TABLE transactions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES users(id) ON DELETE CASCADE,
    holding_id          UUID REFERENCES holdings(id) ON DELETE CASCADE,

    transaction_date    DATE NOT NULL,

    transaction_type    VARCHAR(30) NOT NULL,
    -- Values:
    -- 'buy' | 'sell' | 'sip' | 'sip_cancel'
    -- 'dividend_reinvest' | 'dividend_payout'
    -- 'fd_deposit' | 'fd_maturity' | 'fd_premature_withdrawal'
    -- 'ppf_deposit' | 'ppf_withdrawal'
    -- 'nps_contribution' | 'nps_withdrawal'
    -- 'bonus' | 'rights' | 'split'

    amount              BIGINT NOT NULL,
    -- Positive = money out of pocket (buy/deposit)
    -- Negative = money received (sell/maturity/withdrawal)
    -- Sign convention used directly in XIRR calculation

    units               DECIMAL(15,4),   -- MF units or stock quantity; null for FD/PPF
    price               DECIMAL(12,4),   -- NAV or stock price at transaction; null for FD/PPF

    notes               TEXT,
    import_source       VARCHAR(50),
    -- Values: 'zerodha_csv' | 'groww_csv' | 'cams_cas' | 'kuvera_csv' | 'manual'

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_holding_id ON transactions(holding_id);
CREATE INDEX idx_transactions_date ON transactions(transaction_date);
CREATE INDEX idx_transactions_user_date ON transactions(user_id, transaction_date DESC);

-- ============================================================
-- GOALS (OPTIONAL FEATURE)
-- Nothing in the core system depends on this for a user.
-- Activates conditionally when user creates a goal.
-- ============================================================

CREATE TABLE goals (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                     UUID REFERENCES users(id) ON DELETE CASCADE,

    name                        VARCHAR(255) NOT NULL,
    goal_type                   VARCHAR(50),
    -- Values: 'retirement' | 'house' | 'education' | 'emergency_fund' |
    --         'vehicle' | 'travel' | 'wedding' | 'custom'

    target_amount               BIGINT NOT NULL,       -- INR
    target_date                 DATE NOT NULL,
    monthly_sip_allocated       INTEGER DEFAULT 0,     -- INR/month across linked holdings
    priority                    INTEGER DEFAULT 1,     -- 1 = highest

    -- Monte Carlo simulation results — updated weekly by scheduler
    -- Null until first simulation runs
    success_probability         DECIMAL(5,2),          -- 0-100%
    required_monthly_sip        INTEGER,               -- SIP needed for 90% success
    projected_corpus_p10        BIGINT,                -- pessimistic (10th percentile)
    projected_corpus_p50        BIGINT,                -- median (50th percentile)
    projected_corpus_p90        BIGINT,                -- optimistic (90th percentile)
    last_simulation_at          TIMESTAMPTZ,

    is_active                   BOOLEAN DEFAULT TRUE,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- FUND PORTFOLIO COMPOSITION
-- AMFI monthly portfolio disclosure cache.
-- Used for cross-instrument exposure computation.
-- Updated monthly when AMFI publishes new disclosures.
-- ============================================================

CREATE TABLE fund_compositions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_code         INTEGER NOT NULL,
    company_isin        VARCHAR(20) NOT NULL,
    company_name        VARCHAR(255) NOT NULL,
    weight_pct          DECIMAL(6,3) NOT NULL,   -- company's % weight in the fund
    disclosure_month    DATE NOT NULL,             -- e.g. 2026-04-01 for April 2026 disclosure
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(scheme_code, company_isin, disclosure_month)
);

CREATE INDEX idx_fund_comp_scheme ON fund_compositions(scheme_code, disclosure_month DESC);
CREATE INDEX idx_fund_comp_isin ON fund_compositions(company_isin);

-- ============================================================
-- BUSINESS GROUP MAPPING
-- Maps individual companies to their parent business group.
-- Seeded at startup, updated manually when group structures change.
-- Used for group-level exposure detection.
-- ============================================================

CREATE TABLE business_group_mapping (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_isin        VARCHAR(20) UNIQUE NOT NULL,
    company_name        VARCHAR(255) NOT NULL,
    group_name          VARCHAR(100) NOT NULL,
    -- Values: 'HDFC Group' | 'Tata Group' | 'Adani Group' |
    --         'Reliance Group' | 'Bajaj Group' | 'Mahindra Group' | etc.
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_bgm_group ON business_group_mapping(group_name);
CREATE INDEX idx_bgm_isin ON business_group_mapping(company_isin);

-- ============================================================
-- PORTFOLIO SNAPSHOTS
-- Daily point-in-time record of portfolio value and allocation.
-- Used for historical performance charts and risk metrics.
-- ============================================================

CREATE TABLE portfolio_snapshots (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID REFERENCES users(id) ON DELETE CASCADE,

    snapshot_date           DATE NOT NULL,
    total_value             BIGINT NOT NULL,
    equity_value            BIGINT NOT NULL DEFAULT 0,
    debt_value              BIGINT NOT NULL DEFAULT 0,
    gold_value              BIGINT NOT NULL DEFAULT 0,
    cash_value              BIGINT NOT NULL DEFAULT 0,
    other_value             BIGINT NOT NULL DEFAULT 0,

    equity_pct              DECIMAL(5,2),
    debt_pct                DECIMAL(5,2),
    gold_pct                DECIMAL(5,2),

    portfolio_xirr          DECIMAL(6,2),
    nifty50_return_1y       DECIMAL(6,2),
    nifty500_return_1y      DECIMAL(6,2),

    UNIQUE(user_id, snapshot_date)
);

CREATE INDEX idx_snapshots_user_date ON portfolio_snapshots(user_id, snapshot_date DESC);

-- ============================================================
-- AGENT MEMORY
-- Persistent observations the agent makes about the user.
-- PostgreSQL stores structured data; Qdrant stores embeddings.
-- ============================================================

CREATE TABLE agent_memory (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES users(id) ON DELETE CASCADE,

    memory_type         VARCHAR(50) NOT NULL,
    -- Values: 'risk_observation' | 'preference' | 'goal_context' |
    --         'financial_context' | 'market_view' | 'conversation_summary'

    content             TEXT NOT NULL,
    -- Natural language observation written by the agent
    -- Example: "User expressed concern about debt fund volatility Oct 2024"
    -- Example: "User mentioned house purchase in 3 years, not yet a goal"
    -- Example: "User has irregular income — SIP amount flexibility matters"

    qdrant_point_id     VARCHAR(255),  -- reference to embedding in Qdrant

    confidence          DECIMAL(3,2) DEFAULT 1.0,  -- 0.0 to 1.0
    times_referenced    INTEGER DEFAULT 0,
    last_referenced_at  TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ,   -- some memories expire (market views, time-sensitive)

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_memory_user_id ON agent_memory(user_id);
CREATE INDEX idx_agent_memory_type ON agent_memory(user_id, memory_type);

-- ============================================================
-- ALERTS
-- All proactive alerts. Stored for in-app alert inbox.
-- ============================================================

CREATE TABLE alerts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES users(id) ON DELETE CASCADE,

    alert_type          VARCHAR(50) NOT NULL,
    -- Values: 'rebalancing_drift' | 'fd_maturity' | 'goal_at_risk' |
    --         'tax_opportunity' | 'concentration_risk' |
    --         'stock_underperformance' | 'adverse_news' | 'fund_manager_change'

    severity            VARCHAR(20) NOT NULL,
    -- Values: 'critical' | 'significant' | 'informational'

    title               VARCHAR(255) NOT NULL,
    message             TEXT NOT NULL,
    reasoning           TEXT,          -- full agent reasoning, shown in detail view

    signal_score        INTEGER CHECK (signal_score BETWEEN 1 AND 10),

    related_holding_id  UUID REFERENCES holdings(id) ON DELETE SET NULL,
    related_goal_id     UUID REFERENCES goals(id) ON DELETE SET NULL,
    metadata            JSONB DEFAULT '{}',
    -- For news alert: {"news_headline": "...", "source": "..."}
    -- For drift alert: {"equity_drift": 8.2, "target": 60, "current": 68.2}

    is_read             BOOLEAN DEFAULT FALSE,
    is_acted_upon       BOOLEAN DEFAULT FALSE,
    user_feedback       VARCHAR(20),
    -- Values: 'helpful' | 'not_helpful' | 'already_knew' | 'not_relevant'

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_alerts_user_id ON alerts(user_id);
CREATE INDEX idx_alerts_user_unread ON alerts(user_id, is_read, created_at DESC);

-- ============================================================
-- IMPORT JOBS
-- Tracks CSV import history and status.
-- ============================================================

CREATE TABLE import_jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES users(id) ON DELETE CASCADE,

    source_platform     VARCHAR(50) NOT NULL,
    -- Values: 'zerodha' | 'groww' | 'kuvera' | 'cams_cas' | 'kfintech' | 'generic'

    file_name           VARCHAR(255),
    status              VARCHAR(20) DEFAULT 'pending',
    -- Values: 'pending' | 'processing' | 'preview_ready' | 'completed' | 'failed'

    preview_data        JSONB,         -- parsed holdings awaiting user confirmation
    holdings_created    INTEGER DEFAULT 0,
    holdings_updated    INTEGER DEFAULT 0,
    transactions_created INTEGER DEFAULT 0,
    warnings            JSONB DEFAULT '[]',
    error_message       TEXT,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);
```

### 5a. Metadata JSONB Structure per Instrument Type

This is the contract for the `metadata` column. Each instrument handler is responsible for reading and writing this structure.

**Mutual Fund**
```json
{
  "scheme_code": 120503,
  "isin": "INF879O01019",
  "units": 234.567,
  "average_nav": 89.45,
  "current_nav": 112.30,
  "fund_house": "Parag Parikh Asset Management",
  "category": "Flexi Cap",
  "sub_category": "Multi Cap",
  "is_sip": true,
  "sip_amount": 5000,
  "sip_date": 5,
  "sip_status": "active",
  "folio_number": "12345678"
}
```

**Stock**
```json
{
  "symbol": "RELIANCE.NS",
  "isin": "INE002A01018",
  "exchange": "NSE",
  "quantity": 50,
  "average_price": 2450.00,
  "current_price": 2890.00,
  "sector": "Energy",
  "industry": "Oil & Gas Refining",
  "market_cap_category": "large_cap"
}
```

**Fixed Deposit**
```json
{
  "bank_name": "HDFC Bank",
  "account_number_last4": "4521",
  "principal_amount": 500000,
  "interest_rate": 7.10,
  "compounding_frequency": "quarterly",
  "start_date": "2024-03-15",
  "maturity_date": "2026-03-15",
  "maturity_amount": 576250,
  "is_cumulative": true,
  "is_tax_saving": false,
  "tds_applicable": true
}
```

**PPF**
```json
{
  "bank_name": "SBI",
  "account_number_last4": "7823",
  "current_interest_rate": 7.10,
  "account_opened_date": "2020-04-01",
  "maturity_date": "2035-04-01",
  "lock_in_remaining_years": 9,
  "financial_year_contributions": {
    "2022-23": 150000,
    "2023-24": 150000,
    "2024-25": 120000
  },
  "partial_withdrawal_eligible": false,
  "loan_eligible": true
}
```

**NPS**
```json
{
  "pran": "XXXXXXXXXX",
  "tier": "I",
  "fund_manager": "HDFC Pension",
  "scheme_preference": "active",
  "allocation": {
    "equity_pct": 75,
    "corporate_bond_pct": 15,
    "govt_securities_pct": 10
  },
  "employer_contribution_monthly": 15000,
  "employee_contribution_monthly": 15000
}
```

---

## 6. Agent Design

### Agent Overview

| Agent | LLM Used | Trigger | Responsibility |
|---|---|---|---|
| Orchestrator | Claude Sonnet | Every user message + scheduled runs | Intent detection, task decomposition, routing, synthesis |
| Portfolio Analyser | None (pure Python) | On demand | XIRR, allocation, drift, risk metrics |
| Market Intelligence | Claude Sonnet | On demand | NAV data, macro context, market conditions |
| Goal Tracker | None (pure Python) | Weekly scheduler + on demand | Monte Carlo simulation, goal progress, conflict detection |
| Recommendation | Claude Sonnet | On demand | Generate specific actionable proposals |
| Devil's Advocate | Gemini Flash | After every Recommendation | Critique proposals, find counterarguments |
| Proactive Alert | Gemini Flash | Daily scheduler | Drift, FD maturity, goal risk, concentration |
| News Intelligence | Gemini Flash | Daily scheduler | Fetch and classify news for all holdings |
| Concentration Risk | None (pure Python) | On portfolio update + daily | Single stock, sector, group exposure |

### LangGraph State Schema

Every field that any agent reads or writes must be declared here. Agents communicate only through this state — no direct calls between agents.

```
PunjiState fields:

  Input:
    user_id: str
    user_query: str                    -- empty string for scheduled runs
    run_type: str                      -- 'conversational' | 'scheduled_daily' | 'scheduled_weekly'

  User context (loaded at start of every run):
    risk_profile: dict | None
    active_goals: list[dict]           -- empty list if no goals configured
    agent_memories: list[dict]         -- top-5 from Qdrant semantic search on query

  Intermediate outputs (populated during run):
    intent: str | None
    allocation_report: dict | None
    concentration_report: dict | None
    market_context: dict | None
    goal_analysis: dict | None
    news_alerts: list[dict]
    proposal: dict | None
    critique: dict | None

  Final outputs:
    final_response: str | None
    reasoning_trace: list[str]         -- each agent appends its output summary
    new_memories: list[dict]           -- written to DB after run completes
    alerts_to_create: list[dict]       -- written to alerts table after run

  Control:
    errors: list[str]
    current_agent: str
```

### Orchestrator Agent

The only agent that sees the full state at all times. Responsible for three things: detecting intent, routing to the right agent sequence, and synthesising the final response.

**Intent to agent workflow mapping:**

```
portfolio_overview  →  portfolio_analyser → concentration_risk → respond
portfolio_advice    →  portfolio_analyser → market_intelligence → recommendation → devil_advocate → synthesise
rebalancing         →  portfolio_analyser → market_intelligence → recommendation → devil_advocate → synthesise
goal_check          →  goal_tracker → portfolio_analyser → respond
tax_query           →  portfolio_analyser → respond (with tax analysis)
stock_question      →  market_intelligence → concentration_risk → respond
news_query          →  news_intelligence → respond
fd_advice           →  portfolio_analyser → market_intelligence → recommendation → respond
general_finance     →  market_intelligence → respond
```

**Synthesis rules when combining Recommendation + Devil's Advocate:**
- Critique category 'minor': adopt proposal, acknowledge critique in one sentence
- Critique category 'moderate': moderate the proposal (reduce amount or add condition), acknowledge critique
- Critique category 'critical': significantly revise or recommend holding action, give critique equal weight
- Always: include both proposal reasoning and strongest critique in the final response

### Recommendation Agent — Output Requirements

Every proposal must be concrete. The Orchestrator rejects vague outputs. Required fields in every proposal JSON:

```
action:           'buy' | 'sell' | 'hold' | 'switch' | 'rebalance'
instrument:       specific fund name or stock ticker (never a category)
amount_inr:       specific rupee amount (never a range)
timeline:         'immediate' | 'this_week' | 'this_month' | 'before_<date>'
reasoning:        why this specific instrument and amount
expected_outcome: what this achieves for the portfolio
tax_note:         any STCG/LTCG implications
```

### Devil's Advocate Agent — Critique Framework

Evaluates every proposal across six dimensions. Must rate each: 'critical' | 'moderate' | 'minor' | 'not_applicable'. Must not fabricate concerns — if no valid objection exists, mark 'not_applicable'.

```
Dimension 1 — Timing risk:
  Is current market valuation (Nifty P/E) favourable for this action?

Dimension 2 — Goal conflict:
  Does this increase risk when a goal deadline is approaching?

Dimension 3 — Tax implications:
  Will this trigger STCG that reduces the net benefit?

Dimension 4 — Simpler alternative:
  Is there a lower-cost or lower-risk way to achieve the same outcome?

Dimension 5 — Concentration risk:
  Does this increase exposure to a single stock, sector, or fund house?

Dimension 6 — Liquidity risk:
  Does this lock up capital that may be needed within 12 months?
```

### Proactive Alert Agent — Signal Scoring

The noise filter is the most critical implementation detail. Every potential alert is scored 1–10. Only alerts scoring 7 or above are sent to the user.

```
REBALANCING_DRIFT:
  base = min(abs(equity_drift_pct) / 2, 5)
  + 2 if drift > 10%
  + 1 if market conditions are stable (good time to act on drift)
  + 1 if user not notified in 14+ days
  - 3 if notified within last 7 days
  Threshold: >= 7

FD_MATURITY:
  score = 10 if days_to_maturity <= 7
  score = 7 if days_to_maturity <= 14
  score = 5 if days_to_maturity <= 30
  - 3 if notified within last 14 days
  Threshold: >= 7

GOAL_AT_RISK:
  score = 10 if success_probability < 50
  score = 8 if success_probability < 60
  score = 7 if success_probability < 70
  - 4 if notified within last 3 days
  Threshold: >= 7

CONCENTRATION_RISK:
  score = 9 if single stock > 15% of portfolio
  score = 7 if single stock > 10% of portfolio
  score = 6 if single sector > 35% (does not fire)
  - 3 if notified within last 30 days
  Threshold: >= 7

ADVERSE_NEWS:
  score = 10 if news_category = 'critical'
  score = 7 if news_category = 'significant'
  score = 3 if news_category = 'monitor' (does not fire)
  No cooldown for critical news (always fires for new critical news)
  Threshold: >= 7
```

### News Intelligence Agent

Runs daily for every stock and equity MF holding across all active users.

**Data sources in priority order:**
1. yfinance `.news` attribute — per ticker, free, no limits
2. Google News RSS — `https://news.google.com/rss/search?q={company}+stock+NSE`
3. NewsAPI.org — free tier, pooled carefully across users

**News impact classification categories:**

```
critical:
  SEBI enforcement action, promoter pledging above threshold,
  auditor resignation, sudden CEO/MD exit without succession plan,
  debt default, going concern qualification in audit report,
  regulatory ban on core products

significant:
  Major contract loss (>10% revenue), key customer exit,
  earnings miss >20% vs estimates, significant guidance cut,
  management change at CEO/CFO level, credit rating downgrade,
  sector-wide regulatory headwind

monitor:
  Earnings miss <10%, minor regulatory notice, analyst downgrade,
  minor guidance cut, competitive pressure news

noise:
  Routine quarterly results, general market movement,
  analyst target price adjustments, macro news not company-specific
```

### Concentration Risk Agent

This agent has two distinct responsibilities: simple threshold checks (easy) and cross-instrument exposure detection (the genuinely hard and valuable part).

---

#### Part A — Simple Threshold Checks

```
Single stock direct holding:
  Warning (informational): > 10% of total portfolio
  Alert (significant): > 15% of total portfolio

Single sector (across all direct holdings):
  Warning: > 30% of total portfolio
  Alert: > 35% of total portfolio

Single business group (Tata, Adani, HDFC, Reliance, etc.):
  Covers direct stocks + FDs with that bank/group
  Warning: > 25% of total portfolio
  Alert: > 30% of total portfolio

Fund overlap between two equity MFs:
  Flag when overlap in top-10 holdings > 50%
  Data source: AMFI monthly portfolio disclosure
```

---

#### Part B — Cross-Instrument Exposure Detection

**The core insight:** A user's real exposure to a company is almost always larger than they think. It is hidden across multiple instruments simultaneously — direct stock holding, the same stock inside mutual funds, and institutional exposure via FDs or bonds with that company's group.

**Example that illustrates the problem:**

A user holds:
- HDFC Bank stock directly: 5% of total portfolio
- Parag Parikh Flexi Cap: 20% of portfolio, HDFC Bank is 8% of this fund
- Nifty 50 Index Fund: 15% of portfolio, HDFC Bank is 14% of Nifty 50
- HDFC Bank Fixed Deposit: 10% of portfolio

```
Direct stock exposure:          5.0%
Inside Parag Parikh (20% × 8%): 1.6%
Inside Nifty 50 (15% × 14%):   2.1%
FD institutional exposure:     10.0%
─────────────────────────────────────
Real HDFC Group exposure:      18.7%
```

The user thinks they have 5% in HDFC. They actually have 18.7%. This is the insight Punji delivers that no other app in India provides.

**How to compute it:**

For each company or business group, aggregate exposure across all three layers:

```
Layer 1 — Direct stock holdings
  straightforward: holding.current_value / total_portfolio_value

Layer 2 — Indirect via mutual funds
  For each equity MF holding:
    fetch fund's portfolio composition from AMFI (monthly disclosure)
    find the target company's weight in that fund
    exposure = (fund_weight_in_portfolio × company_weight_in_fund)
  Sum across all MF holdings

Layer 3 — Institutional via FDs and debt instruments
  If user holds FD with HDFC Bank:
    exposure = fd_value / total_portfolio_value
    classification: 'institutional' (different risk profile from equity)
  If user holds debt MF heavily invested in HDFC group bonds:
    compute same as Layer 2 for debt funds

Total real exposure = Layer 1 + Layer 2 + Layer 3
```

**Data source for fund portfolio composition:**

AMFI (Association of Mutual Funds in India) mandates every fund to disclose their full portfolio monthly. This data is publicly available and free.

URL pattern: `https://www.amfiindia.com/spages/NAVAll.txt` for NAV data.

For portfolio holdings: AMFI publishes monthly portfolio disclosures. The implementation should cache this data monthly (it changes only once a month) and build a lookup table: `{scheme_code: {company_isin: weight_pct}}`.

This lookup table is the core data structure that enables Layer 2 computation efficiently.

**Business group mapping:**

Maintain a static mapping of companies to their business groups. This enables group-level exposure detection.

```
HDFC Group:
  HDFC Bank, HDFC Life, HDFC AMC, HDFC Ergo, HDB Financial

Tata Group:
  TCS, Tata Motors, Tata Steel, Titan, Tata Consumer, Tata Power,
  Tata Chemicals, Tata Communications, Indian Hotels, Voltas

Adani Group:
  Adani Enterprises, Adani Ports, Adani Power, Adani Green,
  Adani Total Gas, Adani Wilmar, ACC, Ambuja Cements

Reliance Group:
  Reliance Industries, Jio Financial, Network18

Bajaj Group:
  Bajaj Finance, Bajaj Finserv, Bajaj Auto

Mahindra Group:
  Mahindra & Mahindra, Tech Mahindra, Mahindra Lifespace
```

This mapping is stored as a seeded lookup table in PostgreSQL, updated manually when group structures change.

**Thresholds for cross-instrument exposure alerts:**

```
Single company (real exposure across all layers):
  Warning: > 8% real exposure
  Alert: > 12% real exposure
  Note: lower thresholds than direct-only because hidden exposure is more dangerous

Single business group (real exposure across all layers):
  Warning: > 20% real group exposure
  Alert: > 25% real group exposure

FD + equity combination (same institution):
  Always flag when user holds both equity AND FD with same bank/NBFC
  Reason: FD is supposedly "safe" but if the institution fails,
          both equity AND savings are at risk simultaneously
```

**How it surfaces in the UI:**

The insight is shown in a dedicated "Hidden Exposure" section on the Holdings and Concentration pages.

```
🔍 Hidden Exposure Analysis

HDFC Group — Real exposure: 18.7% of portfolio
  ├── Direct: HDFC Bank stock              5.0%
  ├── Via Parag Parikh Flexi Cap           1.6%  (8% of fund × 20% allocation)
  ├── Via Nifty 50 Index Fund              2.1%  (14% of index × 15% allocation)
  └── FD institutional exposure           10.0%
      ⚠️ You also hold an HDFC Bank FD — if HDFC faces stress,
         both your equity and your "safe" FD are at risk.

Tata Group — Real exposure: 11.2% of portfolio
  ├── Direct: TCS stock                    6.0%
  ├── Via Parag Parikh Flexi Cap           2.1%  (7% of fund × 30% allocation)
  └── Via Nifty 50 Index Fund              3.1%  (21% of index × 15% allocation)
  ℹ️ Within acceptable range — no action needed.
```

**Plain English insight generated by agent:**

When real exposure crosses a threshold, the agent generates a plain-English insight:

> "Your real exposure to HDFC Group is 18.7% of your portfolio — much higher than the 5% you see in your stock holdings alone. This is because HDFC Bank appears in both your Parag Parikh fund and your Nifty 50 index fund, and you also hold an HDFC Bank FD. If HDFC Group faced a serious problem, nearly a fifth of your portfolio would be affected simultaneously. Consider whether this concentration aligns with your risk tolerance."

**Scheduler trigger:** Runs monthly when AMFI publishes new portfolio disclosures, and immediately when a new holding is added.

---

#### Part C — Stock Underperformance Detection

Relative underperformance is signal; absolute price drop is noise.

```
A stock down 10% when market is down 12% = outperforming — no alert
A stock down 10% when its sector is up 5% = significant red flag — alert
```

Detection rule: flag if stock underperforms its own sector by > 15% over 3 months OR underperforms Nifty by > 20% over 3 months.

Compute using yfinance historical data. Sector benchmark: use the relevant Nifty sectoral index (Nifty Bank, Nifty IT, Nifty FMCG, etc.) as the sector proxy.

---

## 7. Holdings Import System

### Design Philosophy

Import is the primary way users add data. It must handle every major Indian platform's format, handle unknown formats via Claude, always show a preview before committing to the database, and handle duplicate detection gracefully.

### Import Flow

```
Step 1: User selects platform
  Dropdown: CAMS CAS | Zerodha | Groww | Kuvera | Upstox | Angel One | Other/Not sure

Step 2: User uploads file
  Accepted: CSV, PDF (CAMS CAS only)
  Max size: 10MB
  File held in memory only — not persisted to disk

Step 3: Format detection and parsing
  Backend checks column headers against known format signatures.
  Known format match → use dedicated parser.
  Unknown format or "Other" selected → Claude-powered generic parser.
  Output: list of HoldingDTO objects with confidence scores.

Step 4: Preview shown to user
  Table of all parsed holdings before anything is saved.
  Low-confidence items flagged for review.
  Unrecognised items shown separately — user can classify or skip.
  User can edit any field in the preview table.

Step 5: User confirms import
  User clicks "Import X holdings".
  Backend writes holdings + transactions to database.
  import_jobs record updated with results.
  Portfolio service triggered: recompute XIRR and allocation.
  Redis Streams event published: import.completed

Step 6: Deduplication check
  Before creating, check if holding already exists.
  Match on: instrument_type + key metadata field (scheme_code for MF, symbol for stock).
  If exists: offer to update units/price rather than create duplicate.
  User confirms per-item deduplication decision.
```

### Platform CSV Format Signatures

Used by format detector. Match by checking required column headers.

```
zerodha_holdings:
  Required: ["Symbol", "ISIN", "Qty.", "Avg. cost", "LTP"]

zerodha_tradebook:
  Required: ["Symbol", "ISIN", "Trade Type", "Quantity", "Price", "Trade Date"]

groww_stocks:
  Required: ["Stock Name", "Quantity", "Average Price", "Current Price", "Invested Value"]

groww_mf:
  Required: ["Fund Name", "Units", "Average NAV", "Current NAV", "Invested Amount"]

kuvera:
  Required: ["Scheme Name", "Folio", "Units", "Average NAV", "Current NAV"]

cams_cas:
  Detection: file first 500 chars contains "Consolidated Account Statement"
  Format: PDF or CSV

kfintech:
  Detection: file first 500 chars contains "KFin Technologies"
```

### Generic Claude Parser

For unknown formats or when user selects "Other/Not sure":
- Send first 3,000 characters of file to Claude Sonnet
- Prompt asks Claude to extract holdings as a JSON array
- Each item: instrument_type, display_name, symbol/scheme_code, quantity/units, average_price/nav, current_price/nav (if present)
- Claude handles variations in column names, number formats, date formats
- All Claude-parsed items get confidence_score = 0.7 (flagged for review)

### CAMS CAS — Special Handling

The CAMS Consolidated Account Statement covers all mutual fund holdings across all platforms in one file. It is the single most valuable data source.

How users obtain it: visit camsonline.com → login with PAN + registered email → request Detailed Account Statement → download or receive by email as PDF.

CAMS CAS parser must handle:
- Multiple folios for the same scheme (consolidate to one holding)
- Transaction history within the statement (populate transactions table for XIRR)
- Multiple fund houses in one file
- Dividend reinvestment transactions
- Both PDF and CSV variants

### Broker Live Connection (v2 — Interface Only in v1)

The `InstrumentConnector` abstract interface is defined in v1 so broker connections can be added in v2 without touching existing code.

Interface: authenticate(auth_code), get_holdings(token), get_transactions(token, from_date), token_is_valid(token).

Only `ZerodhaKiteConnector` stub exists in v1 — not functional. UI shows "Connect Zerodha" button with "Coming soon" state.

Reason for deferral: Zerodha Kite API costs ₹2,000/month in developer fees, tokens expire daily (requiring daily re-auth from users), and CSV import covers 90% of the same use case with zero cost and no UX friction.

---

## 8. Financial Mathematics Engine

All calculations live in `services/portfolio_service.py` as pure Python with no LLM dependency. These are the most critical functions in the codebase. Each must have unit tests with known expected values before integration with agents.

### XIRR

**Why XIRR:** Absolute returns ignore timing of investments. XIRR solves for the annualised rate that makes the net present value of all cashflows zero — the only mathematically correct measure when investments are made at irregular intervals.

**Implementation:** Use `scipy.optimize.brentq` to solve the NPV equation. Sign convention: money invested = positive, money received = negative. Add current portfolio value as a final positive cashflow dated today.

**Formula:** `NPV = sum(cashflow_i / (1 + r)^(days_i / 365)) = 0`. Solve for r.

**Edge cases to handle:** Insufficient transaction history (return None), no valid solution in range (return None), very short investment period (< 30 days, return None).

**Compute at two levels:** Per holding (individual instrument XIRR) and total portfolio (all cashflows combined).

### Monte Carlo Goal Simulation

**Parameters:**
- Simulations: 1,000 per run
- Equity returns: Normal distribution, mean=12%, std=18% (Nifty50 historical)
- Debt returns: Normal distribution, mean=7%, std=3% (debt fund category average)
- Mixed portfolios: weighted average of distributions based on goal's linked holdings asset class mix

**Output:** success_probability (% of simulations reaching target), p10/p50/p90 corpus values, required_monthly_sip for 90% success.

**Recalculation triggers:** Weekly via scheduler. Immediately when user modifies a goal. Immediately when holdings linked to a goal are added or removed.

### Benchmark Comparison

Compare portfolio XIRR against:
- Nifty 50 TRI: yfinance ticker `^NSEI`
- Nifty 500 TRI: yfinance ticker `^NSMIDCP`

Comparison window: from user's first transaction date to today. Display alpha (portfolio XIRR minus benchmark XIRR) prominently. Positive alpha = outperforming.

### Risk Metrics

All require portfolio snapshot history. Display only after 3+ months of history exists.

**Sharpe Ratio:** (portfolio return − risk-free rate) / standard deviation of returns. Risk-free rate = current RBI repo rate (stored in config.py, updated manually when RBI changes rate).

**Max Drawdown:** Maximum peak-to-trough decline in portfolio value over full history. Computed from portfolio_snapshots table.

**Volatility:** Standard deviation of monthly returns from portfolio_snapshots.

### Allocation Engine

Reads ALL active holdings, classifies by asset_class:
- equity_pct = equity holdings / total portfolio value
- debt_pct = debt holdings / total (includes FDs, PPF, debt MFs)
- gold_pct = gold holdings / total
- cash_pct = cash holdings / total

Drift = current % minus target % from risk_profile. Alerts evaluated when drift > 5% in any class.

---

## 9. API Specification

All endpoints require JWT Authorization header unless marked [public].

### Authentication

```
POST /api/auth/register        [public]
  Body: {email, password, full_name}
  Returns: {user_id, access_token, refresh_token}

POST /api/auth/login           [public]
  Body: {email, password}
  Returns: {access_token, refresh_token, user}

POST /api/auth/google          [public]
  Body: {google_id_token}
  Returns: {access_token, refresh_token, user, is_new_user}
  Note: is_new_user=true triggers onboarding redirect on frontend

POST /api/auth/refresh         [public]
  Body: {refresh_token}
  Returns: {access_token}

POST /api/auth/logout
  Body: {refresh_token}
  Returns: {success: true}
```

### Onboarding

```
POST /api/onboarding/risk-profile
  Body: {drawdown_response: 'sell_everything'|'hold'|'buy_more'}
  Returns: {risk_profile, target_allocation}
  Effect: Creates risk_profile, sets onboarding_step=2

GET /api/onboarding/status
  Returns: {onboarding_step, next_step, is_complete}
```

### Portfolio

```
GET /api/portfolio/summary
  Returns: {
    total_value, total_invested, total_pnl_amount, total_pnl_pct,
    portfolio_xirr,
    allocation: {equity_pct, debt_pct, gold_pct, cash_pct},
    drift: {equity_drift, debt_drift, needs_rebalancing},
    benchmarks: {nifty50_xirr, nifty500_xirr, alpha},
    risk_metrics: {sharpe_ratio, max_drawdown, volatility},
    unread_alerts_count,
    has_goals
  }

GET /api/portfolio/allocation
  Returns: {
    current: {equity_pct, debt_pct, gold_pct, cash_pct},
    target: {equity_pct, debt_pct, gold_pct, cash_pct},
    drift: {equity_drift, debt_drift, needs_rebalancing, urgency},
    by_instrument_type: [{instrument_type, value, pct}],
    by_sector: [{sector, value, pct}]
  }

GET /api/portfolio/performance
  Query: period = '1m'|'3m'|'6m'|'1y'|'3y'|'all'
  Returns: {
    portfolio_xirr, absolute_return_pct, absolute_return_amount,
    benchmarks: {nifty50, nifty500},
    alpha,
    chart_data: [{date, portfolio_value, nifty50_value, nifty500_value}]
  }

GET /api/portfolio/concentration
  Returns: {
    -- Simple threshold checks
    stocks: [{symbol, name, value, portfolio_pct, alert_triggered}],
    sectors: [{sector, value, portfolio_pct, alert_triggered}],
    groups: [{group_name, value, portfolio_pct, alert_triggered}],
    fund_overlaps: [{fund1, fund2, overlap_pct}],
    underperformers: [{symbol, stock_return_3m, sector_return_3m, underperformance_pct}],

    -- Cross-instrument exposure (the differentiating feature)
    hidden_exposure: [{
      entity_name,               -- "HDFC Bank" or "HDFC Group"
      entity_type,               -- 'company' | 'group'
      total_real_exposure_pct,   -- 18.7
      alert_triggered,           -- true if above threshold
      breakdown: [{
        source,                  -- "Direct: HDFC Bank stock"
        instrument_type,         -- 'stock' | 'mutual_fund' | 'fd'
        holding_name,            -- "HDFC Bank" or "Parag Parikh Flexi Cap"
        exposure_pct,            -- 5.0 or 1.6
        computation,             -- "8% of fund × 20% portfolio allocation"
      }],
      fd_equity_overlap,         -- true if user holds both FD and equity of same institution
      plain_english_insight      -- agent-generated explanation
    }],
    last_computed_at             -- timestamp of last AMFI data refresh
  }

GET /api/portfolio/snapshots
  Query: from_date, to_date
  Returns: [{date, total_value, equity_pct, debt_pct}]
```

### Holdings

```
GET /api/holdings
  Query: instrument_type (optional), asset_class (optional)
  Returns: [{id, instrument_type, display_name, asset_class,
             invested_amount, current_value, unrealised_pnl, xirr, metadata}]

GET /api/holdings/{id}
  Returns: holding detail + full transaction history

POST /api/holdings
  Body: {instrument_type, display_name, asset_class,
         invested_amount, current_value, metadata, goal_id (optional)}
  Returns: created holding

PUT /api/holdings/{id}
  Body: partial holding fields
  Returns: updated holding

DELETE /api/holdings/{id}
  Effect: sets is_active=false (soft delete, never hard delete)
  Returns: {success: true}

POST /api/holdings/{id}/refresh
  Effect: triggers instrument handler to fetch latest price/NAV
  Returns: {current_value, last_refreshed_at}
```

### Transactions

```
GET /api/transactions
  Query: holding_id (optional), from_date, to_date, page, page_size
  Returns: paginated transactions

POST /api/transactions
  Body: {holding_id, transaction_date, transaction_type,
         amount, units (optional), price (optional), notes (optional)}
  Returns: created transaction
  Effect: triggers XIRR recomputation for that holding

POST /api/transactions/bulk
  Body: [{transaction fields}]
  Returns: {created_count, errors}
```

### Import

```
POST /api/imports/upload
  Body: multipart — file + source_platform
  Returns: {import_job_id, status: 'processing'}

GET /api/imports/{job_id}/preview
  Returns: {
    status,
    holdings_parsed: [{...HoldingDTO, confidence_score}],
    unrecognised_items: [{raw_text, suggested_type}],
    warnings: []
  }

POST /api/imports/{job_id}/confirm
  Body: {
    confirmed_holdings: [{...HoldingDTO, user_confirmed: true}],
    skipped_item_ids: []
  }
  Returns: {holdings_created, holdings_updated, transactions_created}

GET /api/imports/history
  Returns: [{import_job summary}]
```

### Goals

```
GET /api/goals
  Returns: [{goal with latest simulation results}]

POST /api/goals
  Body: {name, goal_type, target_amount, target_date,
         monthly_sip_allocated, priority}
  Returns: created goal (simulation fields null until first run)

PUT /api/goals/{id}
  Returns: updated goal

DELETE /api/goals/{id}
  Effect: sets is_active=false
  Returns: {success: true}

GET /api/goals/{id}/simulation
  Returns: {
    success_probability, required_monthly_sip,
    projected_corpus_p10, projected_corpus_p50, projected_corpus_p90,
    months_to_goal,
    current_trajectory: 'on_track'|'at_risk'|'off_track',
    last_simulation_at
  }

POST /api/goals/{id}/simulate
  Effect: triggers immediate Monte Carlo run (async)
  Returns: {task_id}
```

### Agent and Chat

```
POST /api/agent/chat
  Body: {message}
  Returns: Server-Sent Events stream
  SSE event types:
    {type: 'token', data: 'text chunk'}
    {type: 'reasoning_trace', data: [{agent, output_summary}]}
    {type: 'done', data: {conversation_id}}

GET /api/agent/conversations
  Returns: [{conversation_id, first_message, created_at}]

GET /api/agent/conversations/{id}
  Returns: [{role, content, reasoning_trace, created_at}]

GET /api/agent/memories
  Returns: [{id, memory_type, content, confidence, created_at}]

DELETE /api/agent/memories/{id}
  Effect: removes from agent_memory table AND Qdrant (both must be deleted)
  Returns: {success: true}
```

### Alerts

```
GET /api/alerts
  Query: is_read (optional), alert_type (optional), page, page_size
  Returns: paginated alerts, unread first

PUT /api/alerts/{id}/read
  Returns: {success: true}

POST /api/alerts/{id}/feedback
  Body: {feedback: 'helpful'|'not_helpful'|'already_knew'|'not_relevant'}
  Returns: {success: true}

PUT /api/alerts/read-all
  Returns: {updated_count}
```

### Market Data

```
GET /api/market/mf/{scheme_code}
  Returns: {scheme_name, current_nav, nav_date, fund_house, category, return_1y}

GET /api/market/stock/{symbol}
  Returns: {company_name, current_price, change_pct, sector, market_cap}

GET /api/market/macro
  Returns: {nifty50_pe, nifty50_level, repo_rate, last_updated}

GET /api/market/mf/search?q={query}
  Returns: [{scheme_code, scheme_name, fund_house, category}]

GET /api/market/stock/search?q={query}
  Returns: [{symbol, company_name, exchange, sector}]
```

### Scenarios

```
POST /api/scenarios/simulate
  Body: {
    scenario_name,
    assumption_changes: {
      equity_return_pct: 8,
      debt_return_pct: 6,
      additional_monthly_sip: 5000
    },
    goal_id (optional — if null, runs for all goals)
  }
  Returns: {
    baseline: {goal_results},
    scenario: {goal_results},
    delta: {probability_change, corpus_change, required_adjustment}
  }
```

### WebSocket

```
WS /ws/{user_id}?token={access_token}

Server sends:
  {type: 'alert', data: {alert object}}
  {type: 'import_complete', data: {import_job summary}}
  {type: 'portfolio_refreshed', data: {total_value, allocation}}
  {type: 'ping', data: {timestamp}}

Client sends:
  {type: 'pong'}
```

---

## 10. Frontend Specification

### Design Philosophy

Punji must look and feel like a production-grade enterprise application — not a side project or a hackathon demo. The benchmark is Bloomberg Terminal meets Linear.app: data-dense but never cluttered, dark by default but equally polished in light mode, every interaction intentional.

Three rules that govern every UI decision:

**Rule 1: Data density without clutter.** Financial apps need to show a lot of information. The solution is not to hide data behind clicks — it is to use space, typography, and hierarchy to make density feel organised, not overwhelming.

**Rule 2: Dark mode is first-class, not an afterthought.** The dark theme is the primary design direction. Every colour, shadow, border, and chart colour is defined for dark mode first, then adapted for light mode. Users who prefer light mode get the same quality experience.

**Rule 3: Micro-interactions signal quality.** Hover states, loading skeletons, smooth transitions, number animations — these are what separate a product that feels alive from one that feels static. Every interactive element has a defined hover, focus, active, and loading state.

---

### Design System

#### Colour Tokens

All colours are defined as CSS custom properties on `:root` and overridden under `[data-theme="light"]`. This enables instant theme switching with zero flash.

```css
/* Dark theme (default) */
:root {
  /* Backgrounds — layered from darkest to lightest */
  --bg-base:          #0A0A0F;   /* page background */
  --bg-surface:       #111118;   /* card background */
  --bg-elevated:      #1A1A24;   /* elevated card, modal background */
  --bg-overlay:       #22222F;   /* hover states, dropdown backgrounds */

  /* Borders */
  --border-subtle:    #1E1E2E;   /* table dividers, card borders */
  --border-default:   #2A2A3E;   /* input borders, section dividers */
  --border-strong:    #3A3A54;   /* focused input borders */

  /* Text */
  --text-primary:     #F0F0F8;   /* headings, primary content */
  --text-secondary:   #9898B8;   /* labels, secondary content */
  --text-tertiary:    #5A5A7A;   /* placeholders, disabled states */
  --text-inverse:     #0A0A0F;   /* text on light backgrounds */

  /* Brand */
  --brand-primary:    #6366F1;   /* indigo — primary actions, links */
  --brand-secondary:  #818CF8;   /* lighter indigo — hover states */
  --brand-muted:      #1E1E3F;   /* brand tinted background */

  /* Semantic — Financial */
  --gain:             #22C55E;   /* positive returns, gains */
  --gain-muted:       #14532D;   /* gain background tint */
  --loss:             #EF4444;   /* negative returns, losses */
  --loss-muted:       #450A0A;   /* loss background tint */
  --neutral:          #F59E0B;   /* warnings, drift alerts */
  --neutral-muted:    #451A03;   /* warning background tint */

  /* Semantic — Alerts */
  --alert-critical:   #EF4444;
  --alert-significant:#F59E0B;
  --alert-info:       #6366F1;

  /* Charts — 8-colour accessible palette */
  --chart-1:          #6366F1;   /* indigo */
  --chart-2:          #22C55E;   /* green */
  --chart-3:          #F59E0B;   /* amber */
  --chart-4:          #EC4899;   /* pink */
  --chart-5:          #14B8A6;   /* teal */
  --chart-6:          #F97316;   /* orange */
  --chart-7:          #A855F7;   /* purple */
  --chart-8:          #06B6D4;   /* cyan */
}

/* Light theme override */
[data-theme="light"] {
  --bg-base:          #F8F8FC;
  --bg-surface:       #FFFFFF;
  --bg-elevated:      #F0F0F8;
  --bg-overlay:       #E8E8F4;

  --border-subtle:    #E8E8F4;
  --border-default:   #D4D4E8;
  --border-strong:    #9898B8;

  --text-primary:     #0A0A1A;
  --text-secondary:   #4A4A6A;
  --text-tertiary:    #8A8AAA;
  --text-inverse:     #F0F0F8;

  --brand-primary:    #4F46E5;
  --brand-secondary:  #6366F1;
  --brand-muted:      #EEF2FF;

  --gain:             #16A34A;
  --gain-muted:       #DCFCE7;
  --loss:             #DC2626;
  --loss-muted:       #FEE2E2;
  --neutral:          #D97706;
  --neutral-muted:    #FEF3C7;

  --alert-critical:   #DC2626;
  --alert-significant:#D97706;
  --alert-info:       #4F46E5;
}
```

#### Typography Scale

```css
/* Font families */
--font-body:     'Inter', system-ui, sans-serif;
--font-heading:  'Cal Sans', 'Inter', system-ui, sans-serif;
--font-mono:     'JetBrains Mono', 'Fira Code', monospace;
-- Note: Cal Sans is free and open source at github.com/calcom/font

/* Scale */
--text-xs:    0.75rem  / 1rem     /* 12px — labels, badges */
--text-sm:    0.875rem / 1.25rem  /* 14px — body, table cells */
--text-base:  1rem     / 1.5rem   /* 16px — default body */
--text-lg:    1.125rem / 1.75rem  /* 18px — card titles */
--text-xl:    1.25rem  / 1.75rem  /* 20px — section headings */
--text-2xl:   1.5rem   / 2rem     /* 24px — page headings */
--text-3xl:   1.875rem / 2.25rem  /* 30px — portfolio value display */
--text-4xl:   2.25rem  / 2.5rem   /* 36px — hero numbers */

/* Financial number display — always tabular-nums for alignment */
.financial-number {
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
  font-family: var(--font-mono);
}
```

#### Spacing and Layout

```
Base unit: 4px

Sidebar width:        240px (collapsed: 64px)
Content max-width:    1400px
Card padding:         24px
Section gap:          24px
Component gap:        16px
Border radius:
  sm: 6px    (badges, tags)
  md: 10px   (cards, inputs)
  lg: 14px   (modals, large cards)
  xl: 20px   (panels)
```

#### Elevation and Shadow System

```css
/* Dark mode — shadows use colour, not just opacity */
--shadow-sm:  0 1px 2px rgba(0,0,0,0.4);
--shadow-md:  0 4px 12px rgba(0,0,0,0.5), 0 1px 3px rgba(0,0,0,0.3);
--shadow-lg:  0 8px 24px rgba(0,0,0,0.6), 0 2px 8px rgba(0,0,0,0.4);
--shadow-xl:  0 16px 40px rgba(0,0,0,0.7), 0 4px 16px rgba(0,0,0,0.5);

/* Glow effect for brand elements */
--glow-brand: 0 0 20px rgba(99,102,241,0.25);
```

---

### Theme Switching

Implementation uses `next-themes` library. Zero flash on page load.

Behaviour:
- Default: follows system preference (dark on most modern systems)
- User can override via toggle in top navigation bar
- Preference stored in localStorage, persisted across sessions
- Toggle: sun icon (switch to light) / moon icon (switch to dark)
- Smooth transition: `transition: background-color 150ms ease, color 150ms ease`
- All CSS custom properties update instantly — no page reload

Theme toggle placement: top-right navigation bar, between notifications bell and user avatar.

---

### Application Shell

```
┌────────────────────────────────────────────────────────────────────┐
│ TOPBAR (height: 56px, sticky)                                      │
│ [Punji logo + wordmark]    [Search]    [🔔 3]  [☀️/🌙]  [Avatar] │
├──────────────┬─────────────────────────────────────────────────────┤
│              │                                                      │
│  SIDEBAR     │   MAIN CONTENT AREA                                 │
│  (240px)     │   (max-width: 1400px, centered, padding: 32px)      │
│              │                                                      │
│  Dashboard   │                                                      │
│  Holdings    │                                                      │
│  Goals       │                                                      │
│  Alerts  🔴3 │                                                      │
│  Chat        │                                                      │
│  Scenarios   │                                                      │
│              │                                                      │
│  ──────────  │                                                      │
│  Settings    │                                                      │
│              │                                                      │
└──────────────┴─────────────────────────────────────────────────────┘
```

Sidebar behaviour:
- Desktop: always visible at 240px, collapsible to 64px (icon-only mode)
- Tablet: collapses to icon-only by default, expands on hover
- Mobile: hidden, accessible via hamburger menu → slide-in drawer
- Active item: left border accent in brand colour + text in brand colour + subtle background tint
- Hover: background tint transition 100ms

Topbar:
- Sticky, blurred backdrop: `backdrop-filter: blur(12px)`
- Background: `var(--bg-surface)` at 85% opacity
- Bottom border: `1px solid var(--border-subtle)`
- Search: Command+K opens command palette (search holdings, navigate pages, ask Punji)

---

### Pages

```
Public (no auth):
  /                   Landing page
  /login              Email/password + Google OAuth
  /register           Email/password + Google OAuth

Onboarding (auth required, onboarding_step < 3):
  /onboarding         3-step flow (risk question, add holding, optional goal)

App (auth + onboarding complete):
  /dashboard          Portfolio overview
  /holdings           Holdings management + import
  /goals              Goal tracking + simulation
  /alerts             Alert inbox
  /chat               Conversational agent interface
  /scenarios          What-if scenario simulator
  /settings           Profile, risk profile, agent memory, notifications, theme
```

---

### Component Library — Key Components

All components built on shadcn/ui primitives with Punji design tokens applied. Every component must be implemented in both dark and light variants.

#### Card

```
Background:    var(--bg-surface)
Border:        1px solid var(--border-subtle)
Border radius: 14px
Padding:       24px
Shadow:        var(--shadow-sm)
Hover shadow:  var(--shadow-md) with 200ms transition
```

#### Metric Card (for financial numbers)

Large number display component used throughout dashboard.

```
Structure:
  Label (--text-sm, --text-secondary)
  Large number (--text-3xl or --text-4xl, --font-mono, tabular-nums)
  Delta badge (gain/loss coloured pill with arrow icon)
  Subtext (--text-sm, --text-tertiary)

Example: "Total Portfolio Value / ₹24,85,320 / ▲ ₹18,240 today (+0.74%) / As of 4:15 PM"
```

#### Table

```
Header row:   --bg-elevated, --text-secondary, --text-xs uppercase, letter-spacing 0.05em
Body rows:    --bg-surface background, --border-subtle bottom border
Hover row:    --bg-overlay transition 100ms
Sticky header on scroll
Right-align all numeric columns
Tabular-nums on all financial figures
Sortable columns: sort icon appears on hover, active sort shown always
Empty state: centred illustration + message + CTA button
```

#### Badge / Tag

```
Critical:     background var(--loss-muted), text var(--loss), border none
Significant:  background var(--neutral-muted), text var(--neutral)
Informational:background var(--brand-muted), text var(--brand-secondary)
Success:      background var(--gain-muted), text var(--gain)
Border radius: 6px
Padding:      2px 8px
Font size:    12px, font-weight 500
```

#### Button

```
Primary:   background var(--brand-primary), hover lighten 10%, active darken 10%
Secondary: background var(--bg-elevated), border var(--border-default), hover var(--bg-overlay)
Danger:    background var(--loss-muted), text var(--loss), hover var(--loss) background
Ghost:     no background, hover var(--bg-overlay)

All buttons:
  Border radius: 8px
  Font weight: 500
  Transition: all 150ms ease
  Focus ring: 2px offset ring in brand colour (accessibility)
  Loading state: spinner replaces icon or text
  Disabled state: 40% opacity, cursor not-allowed
```

#### Input / Form Fields

```
Background:     var(--bg-elevated)
Border:         1px solid var(--border-default)
Focus border:   var(--brand-primary) with glow: 0 0 0 3px rgba(99,102,241,0.2)
Border radius:  8px
Padding:        10px 14px
Placeholder:    var(--text-tertiary)
Error state:    border var(--loss), error message below in var(--loss)
```

#### Chart Theming (Recharts)

All chart components must respect the current theme. Implementation:
- Read CSS custom properties in chart components using `getComputedStyle`
- Or pass theme-aware colour arrays from a `useChartColors()` hook
- Grid lines: `var(--border-subtle)`
- Axis labels: `var(--text-tertiary)`, `--text-xs`
- Tooltips: `var(--bg-elevated)` background, `var(--border-default)` border, `var(--shadow-lg)`
- Gain line: `var(--gain)`, Loss line: `var(--loss)`, Neutral: `var(--brand-primary)`

---

### Onboarding Flow

Minimal, single-focus screens. No sidebar or topbar shown during onboarding.

**Step 1 — Risk tolerance**
Full-screen centred layout. Punji logo at top. Progress indicator (Step 1 of 3).
Three large option cards (each ~200px tall) arranged horizontally on desktop, vertically on mobile.
Each card: icon + title + one-line description.
Click any card → immediate API call + navigation to step 2. No submit button.

```
Card A: 😰 "Sell everything"
        "I can't handle seeing my portfolio drop that much"
        → conservative

Card B: 🧘 "Hold and wait"
        "Markets recover — I'll stay the course"
        → moderate

Card C: 🚀 "Buy more"
        "A 30% drop is a buying opportunity"
        → aggressive
```

**Step 2 — Add first holding**
Three option tiles, primary CTA highlighted.

```
┌────────────────────────────────────────────────────┐
│  📄 Import from file          [Recommended]        │
│  The fastest way — supports Zerodha, Groww, CAMS   │
├────────────────────────────────────────────────────┤
│  ✏️ Add manually                                    │
│  Enter one holding at a time                       │
├────────────────────────────────────────────────────┤
│  🔗 Connect broker            [Coming soon]        │
│  Auto-sync with your broker account                │
└────────────────────────────────────────────────────┘
```

**Step 3 — Goals (optional)**
Large "optional" chip at top. Equal-weight buttons at bottom.
No guilt — skipping is framed positively: "You can set goals anytime from your dashboard."

---

### Dashboard

Two-column layout (desktop). Single column (mobile). 32px gap between columns.

**Left column (65%):**

```
Metric Cards row (3 cards side by side):
  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
  │ Total Value   │  │ Total P&L     │  │ Portfolio     │
  │ ₹24,85,320   │  │ ▲ ₹4,85,320  │  │ XIRR          │
  │               │  │ +24.2%       │  │ 14.2%         │
  │               │  │ all time     │  │ vs Nifty 11.8%│
  └───────────────┘  └───────────────┘  └───────────────┘

Performance Chart (full width of left column):
  Line chart — portfolio vs Nifty50 vs Nifty500
  Period tabs: 1M | 3M | 6M | 1Y | 3Y | All
  Smooth area chart, not just line — area fill at 10% opacity
  Crosshair tooltip on hover showing all three values
  Animate in on first load (draw from left to right, 800ms)

Hidden Exposure Panel (if any exposure > threshold):
  Expandable section showing cross-instrument exposure warnings
  Collapsed by default — shows count of exposures found
  "You have 2 hidden concentration risks — tap to review"

Top Holdings Table:
  5 rows, sortable
  Concentration badges inline
  News alert badges inline
  "View all holdings →" footer link
```

**Right column (35%):**

```
Allocation Card:
  Donut chart (180px diameter)
  Legend below: Equity 62% | Debt 28% | Gold 5% | Cash 5%
  Drift indicator per class with coloured arrows
  "Rebalancing needed" — amber banner when drift > 5%
  "Well balanced" — subtle green pill when within range

Goals Card (if user has goals):
  Compact list of active goals
  Per goal: name + circular progress ring + probability chip
  "Retirement 2045 — 73% likely"

Recent Alerts:
  3 most recent unread alerts
  Severity dot + title + time ago
  "View all (12 unread) →"

Quick Ask:
  "Ask Punji anything..." input
  Placeholder rotates between example questions:
    "Should I rebalance this month?"
    "Am I on track for my retirement goal?"
    "Which of my stocks is underperforming?"
  Submits to /chat with message pre-filled
```

---

### Holdings Page

Full-width layout. Three tabs with counts: Mutual Funds (12) | Stocks (8) | Others (3)

Tab switcher: pill-style tabs, not underline tabs.

Table header row includes:
- Bulk select checkbox
- Sort indicators on all columns

Per-row inline indicators (right side of name column):
- 🔴 News alert (adverse news in last 48h) — click to see headline
- 🟡 Concentration risk (> 10% of portfolio)
- 📉 Underperformance (trailing sector by > 15%)
- 🔗 Hidden exposure (this stock appears in your MF holdings too)

Hidden Exposure sub-panel (expandable per row):
```
HDFC Bank ▼
  Your direct holding: 5.0% of portfolio
  Also inside your mutual funds:
    Parag Parikh Flexi Cap (8% of fund × 20% alloc) = 1.6%
    Nifty 50 Index Fund (14% of index × 15% alloc)  = 2.1%
  HDFC Bank FD: 10.0% of portfolio
  ──────────────────────────────────────
  Real total exposure: 18.7% ⚠️
```

Import / Add buttons: top right, consistent across all tabs.

---

### Concentration and Exposure Page

Accessible from Holdings page via "View Exposure Analysis" button or sidebar.

Sections:
1. **Summary cards** — total unique companies exposed to, companies above threshold, groups above threshold
2. **Hidden Exposure table** — sortable by real exposure %, filterable by alert status
3. **Fund Overlap matrix** — grid showing % overlap between each pair of equity MFs held
4. **Business Group breakdown** — treemap or stacked bar showing group-level exposure
5. **Underperformers** — table of stocks underperforming their sector

---

### Chat Interface

Two-panel layout (desktop): conversation history sidebar (280px) + active chat (remaining width).
Mobile: tabs to switch between history and active chat.

Chat input area:
- Pinned to bottom
- Auto-expanding textarea (max 4 lines before scroll)
- Send button right-aligned
- Keyboard shortcut: Enter to send, Shift+Enter for new line
- Suggested prompts shown when input is empty (3-4 rotating suggestions)

Message bubbles:
- User: right-aligned, brand background, white text, 80% max-width
- Agent: left-aligned, surface background, no max-width restriction

Agent message footer:
```
[Show reasoning trace ▼]   [👍]  [👎]   [Copy]
```

Reasoning trace (expandable):
- Styled as a timeline — each agent step is a row with an icon, agent name, and one-line summary
- Monospace font for technical details
- Smooth height animation on expand/collapse

Streaming behaviour:
- Typing indicator (three animated dots) shown while agent is processing
- Tokens stream in character by character with a blinking cursor
- Reasoning trace appears all at once after streaming completes

---

### Alerts Page

Inbox-style layout. Filters bar at top: All | Unread | Critical | Significant | Informational.

Alert card (collapsed):
```
┌─────────────────────────────────────────────────────────────┐
│ 🔴 CRITICAL  Adani Ports — SEBI show-cause notice   2h ago │
│ Your holding: ₹45,000 (3.2% of portfolio)          [Mark read]│
└─────────────────────────────────────────────────────────────┘
```

Alert card (expanded on click):
```
┌─────────────────────────────────────────────────────────────┐
│ 🔴 CRITICAL  Adani Ports — SEBI show-cause notice   2h ago │
│                                                             │
│ SEBI has issued a show-cause notice to Adani Ports         │
│ regarding alleged violations in their FY2024 disclosures.  │
│ This is a regulatory event that directly affects your       │
│ ₹45,000 position (3.2% of portfolio).                      │
│                                                             │
│ Agent reasoning:                                            │
│ News classified as 'critical' — SEBI enforcement           │
│ actions have historically preceded significant price        │
│ corrections in affected companies. Signal score: 10/10.    │
│                                                             │
│ Suggested action: Review your position. Consider whether    │
│ the size of this holding is appropriate given this risk.   │
│                                                             │
│ Was this helpful?  [👍 Yes]  [👎 No]  [I already knew]    │
└─────────────────────────────────────────────────────────────┘
```

---

### Settings Page

Sections in a left-nav layout within the settings page (like Vercel settings UX).

```
Profile              — name, email, profile picture, change password
Appearance           — theme toggle (dark / light / system), font size preference
Risk Profile         — current profile display, retake questionnaire button
Notifications        — email digest toggle, browser notification toggle, alert type preferences
Agent Memory         — table of memories with delete per row, "Clear all memories" button
Import History       — list of past imports: date, platform, items imported, status
Danger Zone          — delete account (with confirmation dialog)
```

Appearance section (most important to implement well):

```
Theme
  ○ Dark (default)
  ○ Light
  ○ System

[Live preview of selected theme — small card showing dashboard colours]
```

---

### Loading States

Every data-fetching operation has a skeleton loading state. No spinners except for actions (button loading states). Skeletons use animated shimmer effect.

```css
@keyframes shimmer {
  0%   { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.skeleton {
  background: linear-gradient(
    90deg,
    var(--bg-overlay) 25%,
    var(--bg-elevated) 50%,
    var(--bg-overlay) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 6px;
}
```

Skeleton shapes mirror the actual content layout exactly — not generic grey bars.

---

### Empty States

Every page and table section has a designed empty state for first-time users.

Pattern:
- Centred illustration (simple SVG, themed)
- Heading: what this section will show
- Subtext: how to get started
- Primary CTA button

Example — Holdings page, no holdings yet:
```
[📊 illustration]
Your portfolio is empty
Import your holdings from Zerodha, Groww, or any broker to get started.
[Import holdings]  [Add manually]
```

---

### Animations and Motion

```
Page transitions:     fade + slight upward slide, 200ms ease-out
Card hover:           shadow elevation + 2px translateY, 150ms ease
Number changes:       count-up animation when values update
Chart mount:          draw animation left to right, 800ms ease-out
Alert appearance:     slide in from right, 300ms spring
Sidebar collapse:     width transition 200ms ease
Modal open:           scale from 0.95 + fade, 200ms ease-out
Skeleton shimmer:     1.5s infinite loop

Reduce motion:        all animations disabled if prefers-reduced-motion
```

---

### Mobile Responsiveness

Breakpoints (same as Tailwind defaults):
- Mobile: < 640px
- Tablet: 640px – 1024px
- Desktop: > 1024px

Key mobile adaptations:
- Sidebar becomes bottom navigation bar (5 icons: Dashboard, Holdings, Alerts, Chat, More)
- Two-column dashboard becomes single column, cards stack vertically
- Tables become card lists (each row is a card, not a table row)
- Charts resize to full width with touch-friendly tooltips
- Chat becomes full screen
- All tap targets minimum 44px × 44px (Apple HIG standard)

---

## 11. Week-by-Week Build Plan

### Pre-work (Before Day 1)

Complete all of these before writing any code:

1. Create GitHub repository
2. Create Railway account, create new project, add PostgreSQL and Redis plugins
3. Create Qdrant Cloud account (free tier at cloud.qdrant.io)
4. Create Google Cloud Console project, enable Google OAuth 2.0, get client ID and secret
5. Get Anthropic API key (claude.ai → API settings)
6. Get Google AI API key (aistudio.google.com) for Gemini Flash
7. Get NewsAPI.org account (free tier)
8. Create `.env` file with all keys — do not commit to git
9. Set up local Docker Compose with PostgreSQL and Redis

### Week 1 — Foundation (Days 1–7)

**Goal: Backend foundation with financial mathematics working. No agents. No frontend.**

Days 1–2: Project scaffold
- FastAPI project structure matching the folder layout in Section 3
- SQLAlchemy async setup, all ORM models
- Alembic configured, all migrations run successfully on Railway
- JWT auth endpoints: register, login, refresh, logout
- Google OAuth endpoint working end-to-end
- Health check endpoint: `GET /health`

Days 3–4: Holdings, transactions, import
- All holdings CRUD endpoints
- Transactions CRUD endpoints
- Import upload, preview, confirm endpoints
- CSV parsers: Zerodha holdings, Groww stocks, Groww MF, Kuvera
- CAMS CAS parser (PDF and CSV variants)
- Generic Claude-powered parser for unknown formats
- Instrument handlers: MutualFundHandler, StockHandler, FixedDepositHandler
- PPF and NPS stubs (no value refresh logic yet)

Days 5–6: Financial mathematics
- XIRR with unit tests (test at least 5 known examples)
- Allocation engine (unified across all instrument types, FDs as debt)
- Drift computation against risk profile targets
- Benchmark comparison via yfinance
- Market data service: MFAPI.in integration, yfinance integration
- Redis caching: 4-hour TTL for NAV data, 15-minute TTL for stock prices
- Concentration risk calculation (single stock, sector, group)
- Portfolio snapshot job in APScheduler (runs daily at midnight)
- AMFI fund composition refresh job (runs monthly on 1st of each month)
  Fetches latest portfolio disclosures from AMFI for all scheme_codes held by any user
  Populates fund_compositions table — used by cross-instrument exposure computation

Day 7: Integration and deploy
- Integration tests for all endpoints
- Manual test: import a real Zerodha CSV, verify XIRR matches a calculator
- Deploy backend to Railway
- Verify all environment variables work in production environment

**Week 1 milestone:** API accepts holdings via CSV import, computes accurate XIRR, allocation, drift, concentration risk, and benchmark comparison.

---

### Week 2 — Agent Layer (Days 8–14)

**Goal: Multi-agent system working with conversational interface.**

Days 8–9: LangGraph setup and Orchestrator
- Install LangGraph, define PunjiState TypedDict
- Orchestrator Agent: intent detection using Claude, routing logic, synthesis logic
- Agent graph: all nodes defined, conditional edges, entry and exit points
- SSE streaming endpoint for chat
- Qdrant client: collection creation, embedding write, semantic search read

Days 10–11: Specialist agents
- Portfolio Analyser Agent (wraps portfolio_service functions)
- Market Intelligence Agent (wraps market_service + adds Claude narrative)
- Goal Tracker Agent (Monte Carlo simulation integrated)
- APScheduler weekly Monte Carlo job

Days 12–13: Recommendation pair
- Recommendation Agent (Claude Sonnet, structured JSON output, specificity enforcement)
- Devil's Advocate Agent (Gemini Flash, six-dimension critique framework)
- Orchestrator synthesis combining both outputs
- Reasoning trace: each agent appends summary to state.reasoning_trace
- Memory write: agent writes key observations to agent_memory + Qdrant after each session

Day 14: Basic frontend
- Next.js + Tailwind setup
- NextAuth with Google + credentials providers
- Login and register pages
- Dashboard page with portfolio summary from API
- Chat page with SSE streaming and reasoning trace display

**Week 2 milestone:** Full conversational agent answering portfolio questions with specific suggestions, devil's advocate critique, and visible reasoning trace. Basic frontend connected to API.

---

### Week 3 — Proactive Intelligence (Days 15–21)

**Goal: App proactively alerts users. News monitoring. Concentration alerts.**

Days 15–16: Event system and proactive alerts
- Redis Streams: publish `portfolio.updated` event on every holding change
- Proactive Alert Agent: all five alert types with signal scoring implemented
- Cooldown tracking per alert type per user
- Alerts table CRUD via API
- APScheduler daily 8 AM job for all users

Days 17–18: News Intelligence
- News Intelligence Agent: yfinance news + Google News RSS integration
- Gemini Flash classification of news by investment impact
- News alert creation with severity levels
- News monitoring integrated into daily scheduler job

Days 19–20: WebSocket + real-time notifications
- WebSocket server: authenticate via token in query param
- Push alerts to connected WebSocket clients
- Frontend WebSocket client: receive and show alerts as toast notifications
- Alert inbox page: severity badges, expand/collapse, feedback buttons

Day 21: Goals feature
- Goals CRUD endpoints fully working
- Goal Tracker Agent Monte Carlo integrated and scheduled
- Goals page on frontend
- Goal progress display: success probability, P10/P50/P90 bar chart
- Goal conflict detection: agent warns when two goals compete for capital

**Week 3 milestone:** Proactive alerts for drift, FD maturity, concentration, and news. WebSocket real-time push. Goals feature working end-to-end.

---

### Week 4 — Polish and Real Users (Days 22–28)

**Goal: Live with real users. Demo-ready.**

Days 22–23: Scenarios and memory UI
- Scenarios endpoint and frontend page
- What-if simulation display: side-by-side baseline vs scenario
- Agent memory page in Settings: display, delete per item
- Memory deletion synced between PostgreSQL and Qdrant

Days 24–25: Frontend polish
- Dashboard: performance line chart, allocation donut chart
- Holdings page: tabs, concentration badges, news alert badges, underperformance badges
- Mobile responsive layout
- Loading states for all async operations
- Empty states for first-time users with no holdings yet

Days 26–27: Onboard real users
- Onboard 15–20 users: friends, college batchmates, Shiprocket colleagues
- Observe first-time user experience — note where friction occurs
- Fix top 3 onboarding friction points
- Add in-app feedback form (simple: thumbs up/down + optional text)

Day 28: Documentation and metrics
- README: project description, architecture diagram, local setup instructions
- Record 3-minute demo video: onboarding → import → dashboard → chat → alert
- Measure and record: total portfolios, total alerts sent, total conversations, approximate total portfolio value tracked

**Week 4 milestone:** Live on Railway with 15+ real users. Demo video recorded. Metrics documented.

---

## 12. Deployment

### Infrastructure Overview

```
Railway project: punji
├── Web service
│   Source: GitHub repo, /backend folder
│   Build: pip install -r requirements.txt
│   Start: alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT
│   Health check: GET /health → 200 OK
│
├── PostgreSQL plugin (Railway auto-provisions)
│   DATABASE_URL injected as environment variable
│
└── Redis plugin (Railway auto-provisions)
    REDIS_URL injected as environment variable

Vercel project: punji-frontend
├── Source: GitHub repo, /frontend folder
├── Framework preset: Next.js (auto-detected)
└── Environment variables set in Vercel dashboard

Qdrant Cloud
└── Free tier at cloud.qdrant.io
    API URL and key stored in Railway env vars
```

### Backend Environment Variables

```
# Auto-injected by Railway
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...

# Set manually in Railway dashboard
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_AI_API_KEY=...
QDRANT_URL=https://...qdrant.io
QDRANT_API_KEY=...
NEWS_API_KEY=...

# Auth
JWT_SECRET=<generate: openssl rand -hex 32>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# App config
ENVIRONMENT=production
FRONTEND_URL=https://punji.vercel.app
CORS_ORIGINS=["https://punji.vercel.app"]

# Feature flags
ENABLE_NEWS_MONITORING=true
ENABLE_GOALS=true
ENABLE_BROKER_CONNECT=false
```

### Frontend Environment Variables

```
# Set in Vercel dashboard
NEXTAUTH_URL=https://punji.vercel.app
NEXTAUTH_SECRET=<generate: openssl rand -hex 32>
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
NEXT_PUBLIC_API_URL=https://punji-backend.railway.app
NEXT_PUBLIC_WS_URL=wss://punji-backend.railway.app
```

### Local Development

```
docker-compose.yml provides:
  postgres:15 → localhost:5432
  redis:7 → localhost:6379

Backend: uvicorn main:app --reload --port 8000
Frontend: npm run dev (port 3000)
```

---

## 13. Cost Reference

### Monthly Cost at 20 Active Users

| Service | Monthly Cost |
|---|---|
| Railway (backend + PostgreSQL + Redis) | $10 |
| Claude Sonnet API (~3 conversations/week/user) | ~$8 |
| Gemini Flash API (daily background runs for all users) | ~$2 |
| Qdrant Cloud (free tier, well under 1GB at this scale) | $0 |
| Vercel (free tier sufficient for this traffic) | $0 |
| NewsAPI.org (100 requests/day free, sufficient for 20 users) | $0 |
| Domain name (annual ÷ 12) | ~₹100 |
| **Total** | **~$20/month** |

### Scaling

| Active Users | Monthly Cost | Per User |
|---|---|---|
| 20 | $20 | $1.00 |
| 100 | $65 | $0.65 |
| 500 | $225 | $0.45 |

### Cost Rules to Follow

1. Always check Redis before calling MFAPI or yfinance (4-hour cache for NAV, 15-minute for stock prices)
2. Use Gemini Flash for all background/scheduled agent work — Claude Sonnet only for user-facing conversational responses
3. Batch news API calls: one daily batch across all users, not per-user per-call
4. XIRR recomputes only when new transactions are added, not on every API call
5. Monte Carlo runs weekly on scheduler, not on every goal page load — cache results in goals table

---

*Punji Technical Specification v2.0*
*Last updated: May 2026*
*Next review: After Week 1 implementation is complete*
