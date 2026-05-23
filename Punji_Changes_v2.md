# Punji — Changes Document

> What needs to change from your existing implementation  
> Read this alongside your existing code — do not rewrite from scratch  
> Every section states: what changed, why, and exactly what to do

---

## How to Use This Document

Each section is self-contained. Read the section, find the corresponding code in your existing implementation, and make only the described changes. Nothing else needs to touch.

Sections are ordered by priority — do them in order.

---

## Change 1: Deployment — Railway → Google Cloud Platform

**What changed:** Everything that was on Railway moves to GCP. You have $300 free credit for 3 months.

**Why:** Better resume signal (Cloud Run, Cloud SQL, Memorystore, Secret Manager vs "Railway"), costs ~$8/month out of pocket vs ~$20, and Gemini Flash calls via Vertex AI are free from your credit.

### Step 1 — Install gcloud CLI and authenticate

```bash
# Mac
brew install google-cloud-sdk

# Windows: download from cloud.google.com/sdk/docs/install

gcloud auth login
gcloud config set project punji-prod
```

### Step 2 — Enable all required APIs (run once)

```bash
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  storage.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com \
  aiplatform.googleapis.com
```

### Step 3 — Create Cloud SQL (replaces Railway PostgreSQL)

```bash
gcloud sql instances create punji-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=asia-south1 \
  --storage-type=SSD \
  --storage-size=10GB \
  --backup-start-time=02:00

gcloud sql databases create punji --instance=punji-db

gcloud sql users create punji_user \
  --instance=punji-db \
  --password=<strong-password-here>
```

Your new DATABASE_URL format for Cloud Run (note: uses Unix socket, not TCP):
```
postgresql+asyncpg://punji_user:<password>@/punji?host=/cloudsql/punji-prod:asia-south1:punji-db
```

### Step 4 — Create Memorystore Redis (replaces Railway Redis)

```bash
gcloud redis instances create punji-redis \
  --size=1 \
  --region=asia-south1 \
  --tier=basic \
  --redis-version=redis_7_0
```

Get the Redis IP after creation:
```bash
gcloud redis instances describe punji-redis --region=asia-south1 | grep host
```

Your new REDIS_URL: `redis://<ip-from-above>:6379`

### Step 5 — Move all secrets to Secret Manager

Do this for every secret. Never put secrets in Cloud Run env vars directly.

```bash
echo -n "your-value" | gcloud secrets create SECRET_NAME --data-file=- --replication-policy=automatic
```

Create these secrets one by one:
```
ANTHROPIC_API_KEY
GOOGLE_AI_API_KEY
QDRANT_URL
QDRANT_API_KEY
NEWS_API_KEY
JWT_SECRET
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
DB_PASSWORD
```

To update a secret later:
```bash
echo -n "new-value" | gcloud secrets versions add SECRET_NAME --data-file=-
```

### Step 6 — Create Artifact Registry

```bash
gcloud artifacts repositories create punji-repo \
  --repository-format=docker \
  --location=asia-south1 \
  --description="Punji backend Docker images"
```

### Step 7 — Add Dockerfile to /backend (if not already present)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT"]
```

### Step 8 — Add cloudbuild.yaml to repo root (new file)

```yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - 'asia-south1-docker.pkg.dev/$PROJECT_ID/punji-repo/backend:$COMMIT_SHA'
      - './backend'

  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - 'asia-south1-docker.pkg.dev/$PROJECT_ID/punji-repo/backend:$COMMIT_SHA'

  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    args:
      - 'gcloud'
      - 'run'
      - 'deploy'
      - 'punji-backend'
      - '--image'
      - 'asia-south1-docker.pkg.dev/$PROJECT_ID/punji-repo/backend:$COMMIT_SHA'
      - '--region'
      - 'asia-south1'
      - '--platform'
      - 'managed'
      - '--allow-unauthenticated'

options:
  logging: CLOUD_LOGGING_ONLY
```

### Step 9 — First manual deploy to Cloud Run

```bash
# Build and push
gcloud builds submit \
  --tag asia-south1-docker.pkg.dev/punji-prod/punji-repo/backend:latest \
  ./backend

# Deploy
gcloud run deploy punji-backend \
  --image asia-south1-docker.pkg.dev/punji-prod/punji-repo/backend:latest \
  --region asia-south1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --add-cloudsql-instances punji-prod:asia-south1:punji-db \
  --set-secrets "ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest,\
GOOGLE_AI_API_KEY=GOOGLE_AI_API_KEY:latest,\
QDRANT_URL=QDRANT_URL:latest,\
QDRANT_API_KEY=QDRANT_API_KEY:latest,\
NEWS_API_KEY=NEWS_API_KEY:latest,\
JWT_SECRET=JWT_SECRET:latest,\
GOOGLE_CLIENT_ID=GOOGLE_CLIENT_ID:latest,\
GOOGLE_CLIENT_SECRET=GOOGLE_CLIENT_SECRET:latest" \
  --set-env-vars "ENVIRONMENT=production,\
DATABASE_URL=postgresql+asyncpg://punji_user:<password>@/punji?host=/cloudsql/punji-prod:asia-south1:punji-db,\
REDIS_URL=redis://<memorystore-ip>:6379,\
FRONTEND_URL=https://punji.vercel.app,\
CORS_ORIGINS=[\"https://punji.vercel.app\"]"
```

### Step 10 — Connect Cloud Build to GitHub (auto-deploy on push)

1. GCP Console → Cloud Build → Triggers
2. Click **Connect Repository** → select GitHub → authorize
3. Select your repo
4. Create trigger:
   - Event: Push to branch
   - Branch: `^main$`
   - Build configuration: `cloudbuild.yaml`

After this, every `git push origin main` auto-deploys. No manual deploys ever again.

### Step 11 — Set billing alert immediately

1. GCP Console → Billing → Budgets & Alerts → Create Budget
2. Budget amount: $300
3. Add alerts at: 50% ($150), 75% ($225), 90% ($270)
4. Email notification to yourself

Do this before anything else to avoid surprise charges after credit expires.

### Step 12 — Update Vercel environment variables

In Vercel dashboard, update:
```
NEXT_PUBLIC_API_URL=https://punji-backend-<hash>-el.a.run.app
NEXT_PUBLIC_WS_URL=wss://punji-backend-<hash>-el.a.run.app
```

Get your Cloud Run URL after first deploy:
```bash
gcloud run services describe punji-backend --region=asia-south1 | grep URL
```

---

## Change 2: Gemini Flash → Vertex AI (free from GCP credit)

**What changed:** Replace direct Gemini API calls with Vertex AI calls for all background agents. Same models, billed to GCP credit instead of a separate Google AI API key.

**Why:** Your GCP credit covers Vertex AI. Devil's Advocate Agent, Proactive Alert Agent, and News Intelligence Agent all use Gemini Flash — moving them to Vertex AI makes them effectively free for 3 months.

**Which agents to change:**
- `agents/devil_advocate.py` — uses Gemini Flash
- `agents/proactive_alert.py` — uses Gemini Flash
- `agents/news_intelligence.py` — uses Gemini Flash

**Keep Claude Sonnet via Anthropic API for:**
- `agents/orchestrator.py`
- `agents/recommendation.py`
- `agents/market_intelligence.py`

### Install Vertex AI SDK

Add to `requirements.txt`:
```
google-cloud-aiplatform>=1.38.0
```

### Change in each affected agent file

Find this pattern (your existing Gemini calls):
```python
import google.generativeai as genai
genai.configure(api_key=settings.GOOGLE_AI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")
response = model.generate_content(prompt)
result = response.text
```

Replace with:
```python
import vertexai
from vertexai.generative_models import GenerativeModel

vertexai.init(project=settings.GCP_PROJECT_ID, location="asia-south1")
model = GenerativeModel("gemini-1.5-flash")
response = model.generate_content(prompt)
result = response.text
```

### Add to config.py

```python
GCP_PROJECT_ID: str = "punji-prod"
```

### Add to Cloud Run deployment (already handled by service account)

Cloud Run automatically authenticates to Vertex AI using the service account — no API key needed. This is one of the advantages of running on GCP.

If you see authentication errors locally during development, run:
```bash
gcloud auth application-default login
```

---

## Change 3: Google OAuth — Google Cloud Console Setup

**What changed:** You now set up OAuth credentials in your existing GCP project (`punji-prod`) instead of creating a separate project.

**Why:** Everything is consolidated in one GCP project.

### In Google Cloud Console

1. Go to `console.cloud.google.com` → select `punji-prod`
2. Left menu → **APIs & Services** → **OAuth consent screen**
3. Click **Get started**
   - App name: `Punji`
   - User support email: your email
   - Audience: **External**
   - Developer contact: your email
   - Accept policy → Create
4. Left menu → **APIs & Services** → **Credentials**
5. Click **+ Create Credentials** → **OAuth client ID**
   - Application type: **Web application**
   - Name: `Punji Web Client`
   - Authorised JavaScript origins:
     ```
     http://localhost:3000
     https://punji.vercel.app
     ```
   - Authorised redirect URIs:
     ```
     http://localhost:3000/api/auth/callback/google
     https://punji.vercel.app/api/auth/callback/google
     ```
6. Click **Create** — copy Client ID and Client Secret immediately (secret shown only once)

### Add test users (required while app is in Testing mode)

APIs & Services → OAuth consent screen → Audience tab → Add test users → add your email and any testers' emails.

### Store credentials in Secret Manager (already created in Change 1)

```bash
echo -n "your-client-id.apps.googleusercontent.com" | \
  gcloud secrets versions add GOOGLE_CLIENT_ID --data-file=-

echo -n "GOCSPX-your-secret" | \
  gcloud secrets versions add GOOGLE_CLIENT_SECRET --data-file=-
```

### Add to backend — new endpoint in routers/auth.py

Add this new route alongside your existing email/password auth routes:

```python
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

@router.post("/api/auth/google")
async def google_auth(body: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    try:
        idinfo = id_token.verify_oauth2_token(
            body.google_id_token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    google_user_id = idinfo["sub"]
    email = idinfo["email"]
    full_name = idinfo.get("name")
    picture = idinfo.get("picture")

    # Find or create user
    result = await db.execute(
        select(User).where(User.google_user_id == google_user_id)
    )
    user = result.scalar_one_or_none()
    is_new_user = False

    if not user:
        # Check if email already registered via email/password
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user:
            # Link Google to existing account
            user.google_user_id = google_user_id
            user.auth_provider = "both"
            user.profile_picture_url = picture
        else:
            # New user
            user = User(
                email=email,
                full_name=full_name,
                profile_picture_url=picture,
                google_user_id=google_user_id,
                auth_provider="google",
                onboarding_step=0
            )
            db.add(user)
            is_new_user = True

        await db.commit()
        await db.refresh(user)

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "is_new_user": is_new_user,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "onboarding_step": user.onboarding_step
        }
    }
```

### Add Pydantic schema

In `schemas/user.py`, add:
```python
class GoogleAuthRequest(BaseModel):
    google_id_token: str
```

### Add to requirements.txt

```
google-auth>=2.28.0
```

### Add to frontend — NextAuth setup

Install:
```bash
npm install next-auth
```

Create `frontend/app/api/auth/[...nextauth]/route.ts`:
```typescript
import NextAuth from "next-auth"
import GoogleProvider from "next-auth/providers/google"

const handler = NextAuth({
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
  ],
  callbacks: {
    async signIn({ user, account }) {
      if (account?.provider === "google") {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL}/api/auth/google`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ google_id_token: account.id_token }),
          }
        )
        if (!res.ok) return false
        const data = await res.json()
        user.backendAccessToken = data.access_token
        user.backendRefreshToken = data.refresh_token
        user.isNewUser = data.is_new_user
      }
      return true
    },
    async jwt({ token, user }) {
      if (user) {
        token.backendAccessToken = user.backendAccessToken
        token.backendRefreshToken = user.backendRefreshToken
        token.isNewUser = user.isNewUser
      }
      return token
    },
    async session({ session, token }) {
      session.backendAccessToken = token.backendAccessToken as string
      session.isNewUser = token.isNewUser as boolean
      return session
    },
  },
  pages: {
    signIn: "/login",
    error: "/login",
  },
})

export { handler as GET, handler as POST }
```

Add to `frontend/types/next-auth.d.ts` (new file — fixes TypeScript errors):
```typescript
import NextAuth from "next-auth"

declare module "next-auth" {
  interface Session {
    backendAccessToken: string
    isNewUser: boolean
  }
  interface User {
    backendAccessToken: string
    backendRefreshToken: string
    isNewUser: boolean
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    backendAccessToken: string
    backendRefreshToken: string
    isNewUser: boolean
  }
}
```

Update your login page — add Google button:
```typescript
import { signIn } from "next-auth/react"

// Add this button to your existing login page
<button onClick={() => signIn("google", { callbackUrl: "/dashboard" })}>
  Continue with Google
</button>
```

Wrap your `frontend/app/layout.tsx` with SessionProvider:
```typescript
import { SessionProvider } from "next-auth/react"

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        <SessionProvider>
          {children}
        </SessionProvider>
      </body>
    </html>
  )
}
```

### Frontend .env.local — add these variables

```
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=<generate: openssl rand -hex 32>
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-secret
```

### Vercel — add same variables in dashboard

```
NEXTAUTH_URL=https://punji.vercel.app
NEXTAUTH_SECRET=<same value as local>
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-secret
```

---

## Change 4: Database Schema — Two New Tables

**What changed:** Two new tables need to be added for the cross-instrument exposure feature.

**Why:** The concentration risk agent needs AMFI fund composition data and business group mappings to compute real exposure across instruments.

### Add Alembic migration

Create a new migration file:
```bash
alembic revision --autogenerate -m "add_fund_compositions_and_business_groups"
```

Or write manually — add these two tables:

```sql
CREATE TABLE fund_compositions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_code         INTEGER NOT NULL,
    company_isin        VARCHAR(20) NOT NULL,
    company_name        VARCHAR(255) NOT NULL,
    weight_pct          DECIMAL(6,3) NOT NULL,
    disclosure_month    DATE NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(scheme_code, company_isin, disclosure_month)
);

CREATE INDEX idx_fund_comp_scheme ON fund_compositions(scheme_code, disclosure_month DESC);
CREATE INDEX idx_fund_comp_isin ON fund_compositions(company_isin);

CREATE TABLE business_group_mapping (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_isin        VARCHAR(20) UNIQUE NOT NULL,
    company_name        VARCHAR(255) NOT NULL,
    group_name          VARCHAR(100) NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_bgm_group ON business_group_mapping(group_name);
CREATE INDEX idx_bgm_isin ON business_group_mapping(company_isin);
```

### Add SQLAlchemy models

In `backend/models/`, create `fund_composition.py`:
```python
from sqlalchemy import Column, String, Integer, Numeric, Date, DateTime
from sqlalchemy.dialects.postgresql import UUID
from database import Base
import uuid
from datetime import datetime

class FundComposition(Base):
    __tablename__ = "fund_compositions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scheme_code = Column(Integer, nullable=False)
    company_isin = Column(String(20), nullable=False)
    company_name = Column(String(255), nullable=False)
    weight_pct = Column(Numeric(6, 3), nullable=False)
    disclosure_month = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class BusinessGroupMapping(Base):
    __tablename__ = "business_group_mapping"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_isin = Column(String(20), unique=True, nullable=False)
    company_name = Column(String(255), nullable=False)
    group_name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
```

### Seed business group mapping

Create `backend/migrations/seed_business_groups.py` and run it once after migration:

```python
BUSINESS_GROUPS = [
    # HDFC Group
    {"isin": "INE040A01034", "name": "HDFC Bank", "group": "HDFC Group"},
    {"isin": "INE795G01014", "name": "HDFC Life Insurance", "group": "HDFC Group"},
    {"isin": "INE127D01025", "name": "HDFC AMC", "group": "HDFC Group"},
    {"isin": "INE001A01036", "name": "HDFC Ltd", "group": "HDFC Group"},

    # Tata Group
    {"isin": "INE467B01029", "name": "TCS", "group": "Tata Group"},
    {"isin": "INE155A01022", "name": "Tata Motors", "group": "Tata Group"},
    {"isin": "INE081A01020", "name": "Tata Steel", "group": "Tata Group"},
    {"isin": "INE280A01028", "name": "Titan Company", "group": "Tata Group"},
    {"isin": "INE192A01025", "name": "Tata Consumer", "group": "Tata Group"},
    {"isin": "INE245A01021", "name": "Tata Power", "group": "Tata Group"},
    {"isin": "INE099A01018", "name": "Tata Chemicals", "group": "Tata Group"},
    {"isin": "INE517H01014", "name": "Indian Hotels", "group": "Tata Group"},
    {"isin": "INE628A01036", "name": "Voltas", "group": "Tata Group"},

    # Adani Group
    {"isin": "INE423A01024", "name": "Adani Enterprises", "group": "Adani Group"},
    {"isin": "INE742F01042", "name": "Adani Ports", "group": "Adani Group"},
    {"isin": "INE814H01011", "name": "Adani Power", "group": "Adani Group"},
    {"isin": "INE364U01010", "name": "Adani Green Energy", "group": "Adani Group"},
    {"isin": "INE399L01023", "name": "Adani Total Gas", "group": "Adani Group"},
    {"isin": "INE418H01029", "name": "ACC", "group": "Adani Group"},
    {"isin": "INE079A01024", "name": "Ambuja Cements", "group": "Adani Group"},

    # Reliance Group
    {"isin": "INE002A01018", "name": "Reliance Industries", "group": "Reliance Group"},
    {"isin": "INE758T01015", "name": "Jio Financial Services", "group": "Reliance Group"},

    # Bajaj Group
    {"isin": "INE296A01024", "name": "Bajaj Finance", "group": "Bajaj Group"},
    {"isin": "INE918I01026", "name": "Bajaj Finserv", "group": "Bajaj Group"},
    {"isin": "INE917I01010", "name": "Bajaj Auto", "group": "Bajaj Group"},

    # Mahindra Group
    {"isin": "INE101A01026", "name": "Mahindra & Mahindra", "group": "Mahindra Group"},
    {"isin": "INE669C01036", "name": "Tech Mahindra", "group": "Mahindra Group"},
]
```

---

## Change 5: New Agent — Concentration Risk with Cross-Instrument Exposure

**What changed:** Your existing concentration risk logic (if any) needs to be extended with three new capabilities: cross-instrument exposure computation, fund overlap detection, and FD+equity same-institution warning.

**Why:** This is one of Punji's strongest differentiators — no mainstream app does this.

### New file: backend/agents/concentration_risk.py

This is a new agent file. Create it from scratch:

```python
"""
Concentration Risk Agent
Computes real exposure across all instrument types for each company/group.
Three parts:
  A — Simple threshold checks (direct holdings only)
  B — Cross-instrument exposure (direct + inside MFs + FD institutional)
  C — Stock underperformance detection
"""

from services.portfolio_service import get_all_active_holdings
from models.fund_composition import FundComposition, BusinessGroupMapping
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date

async def run_concentration_analysis(user_id: str, db: AsyncSession) -> dict:
    holdings = await get_all_active_holdings(user_id, db)
    total_portfolio_value = sum(h.current_value for h in holdings)

    if total_portfolio_value == 0:
        return empty_concentration_report()

    # Part A — Direct threshold checks
    direct_report = compute_direct_thresholds(holdings, total_portfolio_value)

    # Part B — Cross-instrument exposure
    hidden_exposure = await compute_hidden_exposure(
        holdings, total_portfolio_value, db
    )

    # Part C — Underperformance
    underperformers = await compute_underperformers(holdings)

    return {
        "stocks": direct_report["stocks"],
        "sectors": direct_report["sectors"],
        "groups": direct_report["groups"],
        "fund_overlaps": direct_report["fund_overlaps"],
        "hidden_exposure": hidden_exposure,
        "underperformers": underperformers,
        "last_computed_at": date.today().isoformat()
    }


async def compute_hidden_exposure(
    holdings, total_value: int, db: AsyncSession
) -> list[dict]:
    """
    For each company/group: aggregate exposure across
    direct stocks + indirect via MF holdings + FD institutional exposure.
    """
    # Build lookup: {company_isin: group_name}
    group_map = await get_group_mapping(db)

    # Get latest AMFI fund compositions for all held MF scheme codes
    mf_holdings = [h for h in holdings if h.instrument_type == "mutual_fund"]
    scheme_codes = [h.metadata.get("scheme_code") for h in mf_holdings if h.metadata.get("scheme_code")]
    compositions = await get_latest_compositions(scheme_codes, db)
    # compositions: {scheme_code: {company_isin: weight_pct}}

    exposure_map = {}  # {company_isin: {sources: [], total_pct: float}}

    # Layer 1 — Direct stock holdings
    stock_holdings = [h for h in holdings if h.instrument_type == "stock"]
    for holding in stock_holdings:
        isin = holding.metadata.get("isin")
        if not isin:
            continue
        pct = (holding.current_value / total_value) * 100
        _add_exposure(exposure_map, isin, holding.display_name, {
            "source": f"Direct: {holding.display_name}",
            "instrument_type": "stock",
            "holding_name": holding.display_name,
            "exposure_pct": round(pct, 2),
            "computation": f"Direct holding = {round(pct, 2)}% of portfolio"
        })

    # Layer 2 — Indirect via mutual fund holdings
    for mf_holding in mf_holdings:
        scheme_code = mf_holding.metadata.get("scheme_code")
        if not scheme_code or scheme_code not in compositions:
            continue
        fund_portfolio_pct = (mf_holding.current_value / total_value) * 100

        for company_isin, company_weight_in_fund in compositions[scheme_code].items():
            indirect_exposure = (fund_portfolio_pct * company_weight_in_fund) / 100
            company_name = await get_company_name(company_isin, db)
            _add_exposure(exposure_map, company_isin, company_name, {
                "source": f"Via {mf_holding.display_name}",
                "instrument_type": "mutual_fund",
                "holding_name": mf_holding.display_name,
                "exposure_pct": round(indirect_exposure, 2),
                "computation": (
                    f"{company_weight_in_fund}% of fund × "
                    f"{round(fund_portfolio_pct, 1)}% portfolio allocation"
                )
            })

    # Layer 3 — FD institutional exposure
    fd_holdings = [h for h in holdings if h.instrument_type == "fixed_deposit"]
    for fd in fd_holdings:
        bank_name = fd.metadata.get("bank_name", "")
        # Match bank to an ISIN in our group mapping
        bank_isin = find_bank_isin(bank_name, group_map)
        if bank_isin:
            pct = (fd.current_value / total_value) * 100
            _add_exposure(exposure_map, bank_isin, bank_name, {
                "source": f"FD: {bank_name}",
                "instrument_type": "fixed_deposit",
                "holding_name": fd.display_name,
                "exposure_pct": round(pct, 2),
                "computation": f"FD institutional exposure = {round(pct, 2)}% of portfolio"
            })

    # Build final output — only entities above 3% total exposure
    result = []
    for isin, data in exposure_map.items():
        total_pct = sum(s["exposure_pct"] for s in data["sources"])
        if total_pct < 3.0:
            continue  # filter noise

        group_name = group_map.get(isin)
        alert_triggered = total_pct > 8.0  # cross-instrument threshold

        # Check FD + equity overlap
        types_present = {s["instrument_type"] for s in data["sources"]}
        fd_equity_overlap = "fixed_deposit" in types_present and (
            "stock" in types_present or "mutual_fund" in types_present
        )

        result.append({
            "entity_name": data["name"],
            "entity_isin": isin,
            "entity_type": "group" if group_name else "company",
            "group_name": group_name,
            "total_real_exposure_pct": round(total_pct, 2),
            "alert_triggered": alert_triggered,
            "breakdown": data["sources"],
            "fd_equity_overlap": fd_equity_overlap,
        })

    # Sort by total exposure descending
    return sorted(result, key=lambda x: x["total_real_exposure_pct"], reverse=True)


def _add_exposure(exposure_map: dict, isin: str, name: str, source: dict):
    if isin not in exposure_map:
        exposure_map[isin] = {"name": name, "sources": []}
    exposure_map[isin]["sources"].append(source)
```

### New API endpoint — add to routers/holdings.py or a new routers/concentration.py

```python
@router.get("/api/portfolio/concentration")
async def get_concentration(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await run_concentration_analysis(user.id, db)
```

### New scheduler job — add to scheduler/jobs.py

```python
# Monthly on 1st — refresh AMFI fund compositions
@scheduler.scheduled_job('cron', day=1, hour=3, minute=0, timezone='Asia/Kolkata')
async def refresh_amfi_compositions():
    """
    Fetches AMFI monthly portfolio disclosures for all scheme codes
    currently held by any active user.
    """
    scheme_codes = await db.execute(
        "SELECT DISTINCT (metadata->>'scheme_code')::int FROM holdings "
        "WHERE instrument_type = 'mutual_fund' AND is_active = true "
        "AND metadata->>'scheme_code' IS NOT NULL"
    )
    for code in scheme_codes:
        compositions = await fetch_amfi_composition(code)
        await upsert_fund_composition(code, compositions)
```

---

## Change 6: Frontend — Dark Mode + Design System

**What changed:** The frontend needs a proper design token system and dark/light mode toggle. This is a significant frontend change if you haven't already implemented it.

**Why:** Enterprise-grade appearance is a differentiator when demoing to interviewers and real users.

### Install new dependencies

```bash
npm install next-themes framer-motion lucide-react
npx shadcn-ui@latest init
```

When shadcn asks:
- Style: Default
- Base color: Slate
- CSS variables: Yes

### Add CSS variables to globals.css

Replace or extend your existing `frontend/app/globals.css` with the full token system. Add this at the top:

```css
:root {
  --bg-base:          #0A0A0F;
  --bg-surface:       #111118;
  --bg-elevated:      #1A1A24;
  --bg-overlay:       #22222F;

  --border-subtle:    #1E1E2E;
  --border-default:   #2A2A3E;
  --border-strong:    #3A3A54;

  --text-primary:     #F0F0F8;
  --text-secondary:   #9898B8;
  --text-tertiary:    #5A5A7A;
  --text-inverse:     #0A0A0F;

  --brand-primary:    #6366F1;
  --brand-secondary:  #818CF8;
  --brand-muted:      #1E1E3F;

  --gain:             #22C55E;
  --gain-muted:       #14532D;
  --loss:             #EF4444;
  --loss-muted:       #450A0A;
  --neutral:          #F59E0B;
  --neutral-muted:    #451A03;

  --chart-1: #6366F1;
  --chart-2: #22C55E;
  --chart-3: #F59E0B;
  --chart-4: #EC4899;
  --chart-5: #14B8A6;
  --chart-6: #F97316;
  --chart-7: #A855F7;
  --chart-8: #06B6D4;
}

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
}

/* Smooth theme transition */
* {
  transition: background-color 150ms ease, border-color 150ms ease;
}

/* Financial numbers always tabular */
.financial-number {
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
}

/* Skeleton shimmer */
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

### Wrap root layout with ThemeProvider

Update `frontend/app/layout.tsx`:

```typescript
import { ThemeProvider } from "next-themes"
import { SessionProvider } from "next-auth/react"

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider
          attribute="data-theme"
          defaultTheme="dark"
          enableSystem
          disableTransitionOnChange={false}
        >
          <SessionProvider>
            {children}
          </SessionProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
```

Note: `suppressHydrationWarning` on `<html>` is required — next-themes adds `data-theme` attribute server-side which can cause hydration mismatch without it.

### Add theme toggle component

Create `frontend/components/ui/ThemeToggle.tsx`:

```typescript
"use client"
import { useTheme } from "next-themes"
import { Sun, Moon } from "lucide-react"
import { useEffect, useState } from "react"

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  // Avoid hydration mismatch — render only after mount
  useEffect(() => setMounted(true), [])
  if (!mounted) return <div className="w-9 h-9" />

  return (
    <button
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      className="w-9 h-9 flex items-center justify-center rounded-lg
                 hover:bg-[var(--bg-overlay)] transition-colors"
      aria-label="Toggle theme"
    >
      {theme === "dark"
        ? <Sun size={18} className="text-[var(--text-secondary)]" />
        : <Moon size={18} className="text-[var(--text-secondary)]" />
      }
    </button>
  )
}
```

### Add ThemeToggle to your topbar/navbar

Find your existing topbar/navbar component and add:
```typescript
import { ThemeToggle } from "@/components/ui/ThemeToggle"

// Inside topbar JSX, between notifications bell and user avatar:
<ThemeToggle />
```

### Add theme preference to Settings page

In your settings page, add an Appearance section:

```typescript
import { useTheme } from "next-themes"

function AppearanceSection() {
  const { theme, setTheme } = useTheme()

  return (
    <div>
      <h3>Appearance</h3>
      <div className="flex gap-3 mt-4">
        {["dark", "light", "system"].map((t) => (
          <button
            key={t}
            onClick={() => setTheme(t)}
            className={`px-4 py-2 rounded-lg border capitalize
              ${theme === t
                ? "border-[var(--brand-primary)] text-[var(--brand-primary)] bg-[var(--brand-muted)]"
                : "border-[var(--border-default)] text-[var(--text-secondary)]"
              }`}
          >
            {t}
          </button>
        ))}
      </div>
    </div>
  )
}
```

### Update Recharts to respect theme

Wherever you use Recharts charts, pass theme-aware colours. Create a hook:

```typescript
// frontend/lib/useChartColors.ts
"use client"
import { useTheme } from "next-themes"

export function useChartColors() {
  const { resolvedTheme } = useTheme()
  const isDark = resolvedTheme === "dark"

  return {
    grid: isDark ? "#1E1E2E" : "#E8E8F4",
    axis: isDark ? "#5A5A7A" : "#8A8AAA",
    tooltip: {
      bg: isDark ? "#1A1A24" : "#FFFFFF",
      border: isDark ? "#2A2A3E" : "#D4D4E8",
    },
    gain: isDark ? "#22C55E" : "#16A34A",
    loss: isDark ? "#EF4444" : "#DC2626",
    brand: isDark ? "#6366F1" : "#4F46E5",
    charts: ["#6366F1", "#22C55E", "#F59E0B", "#EC4899",
             "#14B8A6", "#F97316", "#A855F7", "#06B6D4"],
  }
}
```

Use in chart components:
```typescript
const colors = useChartColors()

<LineChart data={data}>
  <CartesianGrid stroke={colors.grid} />
  <XAxis tick={{ fill: colors.axis, fontSize: 12 }} />
  <YAxis tick={{ fill: colors.axis, fontSize: 12 }} />
  <Tooltip
    contentStyle={{
      backgroundColor: colors.tooltip.bg,
      border: `1px solid ${colors.tooltip.border}`,
    }}
  />
  <Line stroke={colors.brand} />
</LineChart>
```

---

## Change 7: Local Development — Update .env files

**What changed:** New variables needed for GCP, Vertex AI, and Google OAuth.

### backend/.env (local development)

Add these new variables alongside your existing ones:
```
# GCP
GCP_PROJECT_ID=punji-prod

# Google OAuth (backend only needs CLIENT_ID for token verification)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com

# Vertex AI auth (local only — Cloud Run uses service account automatically)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json
```

For local Vertex AI auth:
```bash
# Easiest option — use your own Google account
gcloud auth application-default login
# This writes credentials to ~/.config/gcloud/application_default_credentials.json
# No GOOGLE_APPLICATION_CREDENTIALS env var needed after this
```

### frontend/.env.local

Add these new variables:
```
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=<generate: openssl rand -hex 32>
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-secret
```

---

## Summary — What Files Change

| File | Change type | Priority |
|---|---|---|
| `cloudbuild.yaml` | New file | Do first |
| `backend/Dockerfile` | New file | Do first |
| `backend/requirements.txt` | Add google-auth, google-cloud-aiplatform | Week 1 |
| `backend/config.py` | Add GCP_PROJECT_ID | Week 1 |
| `backend/routers/auth.py` | Add google_auth endpoint | Week 1 |
| `backend/schemas/user.py` | Add GoogleAuthRequest schema | Week 1 |
| `backend/agents/devil_advocate.py` | Gemini → Vertex AI | Week 1 |
| `backend/agents/proactive_alert.py` | Gemini → Vertex AI | Week 1 |
| `backend/agents/news_intelligence.py` | Gemini → Vertex AI | Week 1 |
| `backend/agents/concentration_risk.py` | New file (cross-instrument exposure) | Week 3 |
| `backend/models/fund_composition.py` | New file | Week 3 |
| `backend/migrations/seed_business_groups.py` | New seed file | Week 3 |
| `backend/scheduler/jobs.py` | Add AMFI monthly refresh job | Week 3 |
| `backend/routers/holdings.py` | Add concentration endpoint | Week 3 |
| `frontend/app/api/auth/[...nextauth]/route.ts` | New file | Week 2 |
| `frontend/types/next-auth.d.ts` | New file | Week 2 |
| `frontend/app/layout.tsx` | Add ThemeProvider + SessionProvider | Week 2 |
| `frontend/app/globals.css` | Add full CSS token system | Week 2 |
| `frontend/components/ui/ThemeToggle.tsx` | New component | Week 2 |
| `frontend/lib/useChartColors.ts` | New hook | Week 2 |
| `frontend/app/(auth)/login/page.tsx` | Add Google sign-in button | Week 2 |
| `frontend/app/(app)/settings/page.tsx` | Add Appearance section | Week 4 |
| `backend/.env` | Add GCP_PROJECT_ID, GOOGLE_CLIENT_ID | Immediate |
| `frontend/.env.local` | Add NEXTAUTH_* and GOOGLE_* vars | Immediate |

---

*Punji Changes Document — v1.0*
*Apply these changes to your existing implementation in the order listed*
