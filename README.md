# Affiliate Adoption Portal

A multi-level affiliate platform for driving adoption of **Meridian** (product
intelligence engine for aspiring entrepreneurs) through personal networks.
Affiliates share referral links, recruit sub-affiliates, track every visit →
signup → trial → subscription through Meridian webhooks, and earn cascading
commissions — all from a gamified dashboard.

**Stack:** FastAPI (Python 3.12) · React + Vite + Tailwind · SQLAlchemy
(Postgres in prod, sqlite for zero-setup dev) · deployable to **Azure
Functions** (API) + **Azure Static Web Apps** (frontend).

---

## What's inside

| Capability | Where |
|---|---|
| Admin creates products (name, description, URL, pricing, commission rates) | Admin console → Products |
| Admin creates the first (root) affiliate users & assigns products | Admin console → Users |
| Affiliates log in, see assigned products, generate unique referral links | Dashboard |
| `?channel=<slug>` attribution — cookied on visit, carried through the funnel | `/r/<slug>` redirect + Meridian cookie |
| Slug encodes the affiliate id **and all parents** (`1-4-9~x7kq`) | `backend/app/services/slugs.py` |
| Webhook events from Meridian: visited / signed_up / trial_started / subscribed / renewed | `POST /api/webhooks/meridian/{product_id}` (HMAC-signed) |
| Per-event outbound callbacks to each affiliate's own URL, JSON or form format | Webhooks page |
| Commissions: ₹0 visit · ₹100 signup · ₹300 trial · 20% of subscription, recurring | `backend/app/services/commission.py` |
| Recursive network: sub-affiliate keeps 80%, 20% cascades up — company cost constant | same |
| Referred-user dashboard with statuses and per-user earnings | Product page |
| Network graph + leaderboard: what every descendant earns *you* | Network page |
| Affiliates invite sub-affiliates by email (signup link) | My Team page |
| Monthly bill generation → submit → admin runs payout cycle → all paid | Payouts + Admin console |
| Gamification: XP, ranks (Spark → Legend), funnel bars, progress | Dashboard |

Commission cascade example (base ₹100, chain A → B → C):
C converts → **C ₹80, B ₹16, A ₹4** (sums to the base — the company never
pays more than the single-affiliate cost). Full math and webhook contract:
[docs/MERIDIAN_INTEGRATION.md](docs/MERIDIAN_INTEGRATION.md).

---

## Quickstart (local, zero config)

Prereqs: Python 3.11/3.12, Node 18+.

```bash
# 1. Backend (sqlite by default — nothing to install besides pip deps)
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m scripts.seed          # demo admin + product + 3-level network + events
uvicorn app.main:app --reload --port 8000
```

```bash
# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173 (proxies /api + /r to :8000)
```

**Demo logins** (seeded):

| Role | Email | Password |
|---|---|---|
| Admin | `admin@portal.local` | `admin123` |
| Root affiliate | `ananya@demo.in` | `demo123` |
| L1 affiliates | `rohan@demo.in`, `priya@demo.in` | `demo123` |
| L2 affiliate | `kabir@demo.in` | `demo123` |

Run tests: `cd backend && python -m pytest tests/ -q` (covers the full flow:
product → network → signed webhooks → cascade → invoice → payout).

Optional Postgres instead of sqlite:

```bash
docker compose up -d
export DATABASE_URL=postgresql+psycopg2://portal:portal@localhost:5432/portal
```

### Simulating Meridian events locally

Grab the product's webhook URL + secret from the Admin console, then:

```bash
BODY='{"event":"signed_up","channel":"<slug-from-your-link>","user_id":"u42","email":"x@y.in"}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "<webhook_secret>" | awk '{print $2}')
curl -X POST http://localhost:8000/api/webhooks/meridian/1 \
  -H "Content-Type: application/json" -H "X-Meridian-Signature: $SIG" -d "$BODY"
```

---

## Deploying to Azure (scalable)

The API is a single ASGI app wrapped by `func.AsgiFunctionApp`
([backend/function_app.py](backend/function_app.py)) — stateless, so the
Functions Consumption/Flex plan scales it out automatically with load. State
lives in Azure Database for PostgreSQL.

Full step-by-step (resource creation, app settings, Static Web Apps, CORS,
scaling notes): **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**. Short version:

```bash
# API
cd backend
az group create -n affiliate-portal -l centralindia
az storage account create -n affportalstore -g affiliate-portal -l centralindia --sku Standard_LRS
az functionapp create -n affiliate-portal-api -g affiliate-portal \
  --storage-account affportalstore --consumption-plan-location centralindia \
  --runtime python --runtime-version 3.12 --functions-version 4 --os-type linux
az functionapp config appsettings set -n affiliate-portal-api -g affiliate-portal --settings \
  DATABASE_URL="postgresql+psycopg2://…" JWT_SECRET="$(openssl rand -hex 32)" \
  PORTAL_BASE_URL="https://affiliate-portal-api.azurewebsites.net" \
  FRONTEND_URL="https://<your-swa>.azurestaticapps.net" \
  CORS_ORIGINS="https://<your-swa>.azurestaticapps.net"
func azure functionapp publish affiliate-portal-api

# Frontend
cd ../frontend
VITE_API_URL=https://affiliate-portal-api.azurewebsites.net npm run build
npx @azure/static-web-apps-cli deploy ./dist --deployment-token <token> --env production
```

---

## Repo layout

```
backend/
  function_app.py          Azure Functions ASGI entrypoint
  app/
    main.py                FastAPI app factory (interface layer)
    routers/               thin HTTP controllers per bounded context
    services/              framework-free domain services:
      commission.py          attribution + multi-level cascade engine
      payout.py              monthly billing & payout cycle
      dispatcher.py          outbound webhook fan-out (build ≠ send)
      slugs.py               network-encoding referral slugs
    models.py              persistence model (SQLAlchemy)
    schemas.py             API contracts (pydantic)
  scripts/seed.py          demo data
  tests/                   commission math + end-to-end flow
frontend/
  src/pages/               Dashboard, Product, Network, Team, Payouts, Webhooks, Admin
  src/components/          Layout, NetworkGraph (SVG tree), UI kit
docs/
  ARCHITECTURE.md          bounded contexts, DDD/SOLID mapping, scaling
  MERIDIAN_INTEGRATION.md  webhook contract + commission math
  DEPLOYMENT.md            Azure step-by-step
```

UI design follows [impeccable](https://github.com/pbakaus/impeccable)
principles: distinctive type (Space Grotesk/Sora, no default stacks), tinted
darks instead of pure gray, one accent system (mint + gold) instead of
gradient soup, no cards-in-cards, restrained 150–500 ms motion.
