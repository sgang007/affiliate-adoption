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
| Admin creates products (URL, pricing, **network commission %**) and is auto-added as the network root | Admin console → Products |
| **Incentive rules** per event: flat ₹ or % of any payload field (`params.subscription`) | Admin console → ⚖ Incentive rules |
| **Event message templates** (visited/signed_up/trial/subscribed params), admin-editable | Admin console → ✉ Event messages |
| **Integration prompt generator**: one copy-paste doc with channel caching, `referrer_id` column, formats & secret | Admin console → ⚡ Integration prompt |
| Affiliate identity: hex hash of email = the `?channel=` id on every link | `backend/app/services/identity.py` |
| Webhook ingestion `{channel, event, params}`, HMAC-signed, idempotent | `POST /api/webhooks/meridian/{product_id}` |
| Invite emails + payout confirmations via Resend (SMTP fallback), invite join-status, per-member funnel stats | My Team page |
| Top-down distribution: admin earns ₹0; each level takes network % of the pool, converter keeps the rest | `backend/app/services/commission.py` |
| Referred-user dashboard with statuses and per-user earnings | Product page |
| Network graph + leaderboard: what every descendant earns *you* | Network page |
| Admin and affiliates invite sub-affiliates by email (signup link) | My Team page |
| **Ledger + payout requests**: request with UPI/bank → admin approves → marks paid → email sent | Payouts + Admin console |
| Gamification: XP, ranks (Spark → Legend), funnel bars, progress | Dashboard |

Distribution example (flat ₹300 rule, 20% network commission, chain
A admin → B → C → D, D's link converts): **B ₹60 · C ₹48 · D ₹192** — sums
to the payable, the company never pays more, and the admin earns nothing.
Full contract: [docs/MERIDIAN_INTEGRATION.md](docs/MERIDIAN_INTEGRATION.md).

---

## Quickstart (local, zero config)

Prereqs: Python 3.11/3.12, Node 18+.

```bash
# 1. Backend (sqlite by default — nothing to install besides pip deps)
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

First startup creates the tables and exactly one login: the admin, taken
from the `ADMIN_EMAIL` / `ADMIN_PASSWORD` environment variables (defaults
`admin@portal.local` / `admin123`; set them in `backend/.env` locally or as
app settings in deployment). Everything else — products, rules, affiliates,
the network — you create from the Admin console.

Optional: `python -m scripts.seed` populates a demo product, a 4-affiliate
network and a funnel event stream if you ever want pre-filled dashboards.

```bash
# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173 (proxies /api + /r to :8000)
```

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
