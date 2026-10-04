# Architecture

## Bounded contexts

| Context | Responsibility | Code |
|---|---|---|
| **Identity & Network** | users, roles, invites, the materialized-path network tree | `models.User/Invite`, `routers/auth.py`, `routers/team.py` |
| **Catalog** | products, pricing, commission rates, assignments | `models.Product/ProductAssignment`, `routers/admin.py` |
| **Tracking & Attribution** | referral links, channel slugs, visits, referred users, funnel status | `models.AffiliateLink/ReferredUser/Event`, `routers/webhooks_in.py`, `services/slugs.py` |
| **Commissions** | the cascade engine — the heart of the domain | `services/commission.py`, `models.Commission` |
| **Billing & Payouts** | monthly bills, submission, payout cycles | `services/payout.py`, `models.Invoice`, `routers/invoices.py` |
| **Integrations** | inbound Meridian webhooks, outbound affiliate callbacks, email | `services/dispatcher.py`, `services/emailer.py` |

## Layering (dependency rule: outer → inner only)

```
HTTP (FastAPI routers, pydantic schemas)      ← interface layer
        ↓
Domain services (commission, payout,          ← pure business rules;
dispatcher.build_deliveries, slugs)              no FastAPI imports
        ↓
Persistence (SQLAlchemy models, Session)      ← infrastructure
```

- Routers are thin controllers: parse/authorize, call a domain service,
  shape the response. No business rules live in HTTP handlers.
- Domain services raise plain Python errors (`ValueError`, `LookupError`);
  routers translate them to HTTP codes — the domain never knows about HTTP.
- Side effects are separated from decisions: `dispatcher.build_deliveries`
  (pure, testable) vs `dispatcher.send_deliveries` (I/O, fire-and-forget).

## SOLID mapping

- **S** — each service owns one reason to change: cascade math
  (`commission.py`), billing (`payout.py`), fan-out (`dispatcher.py`),
  slug policy (`slugs.py`), transport (`routers/*`).
- **O** — new inbound event types are added via the `EVENT_STATUS` /
  `EVENT_COMMISSION` maps; new outbound formats via the format branch in the
  dispatcher — no engine changes.
- **L** — admin vs affiliate share the `User` aggregate; role-specific
  behavior is enforced at the boundary (`deps.require_admin`), not by
  subclassing.
- **I** — clients see narrow contracts (pydantic schemas per use case), not
  the persistence model.
- **D** — routers depend on abstractions provided by FastAPI DI
  (`get_db`, `get_current_user`); the DB engine is injected from config, so
  sqlite/Postgres swap without code changes. The pragmatic trade-off: domain
  services accept a `Session` rather than hand-rolled repository interfaces —
  the seam to introduce repositories later is the service signature.

## Key domain decisions

- **Network as materialized path** (`User.path = "1/4/9"`): one indexed
  string gives O(1) ancestor chains for cascades and `LIKE 'path/%'`
  subtree queries for dashboards — no recursive CTEs needed, scales to deep
  networks.
- **Slug encodes the lineage**: `1-4-9~x7kq` = base36 ancestor ids + nonce.
  Attribution survives even if DB rows move, and links are self-describing.
- **Company cost invariant**: every paid event distributes exactly the base
  amount. Converting affiliate keeps 80%, each ancestor keeps 80% of what
  arrives, root keeps the remainder. Proven in `tests/test_commission_math.py`
  for arbitrary depth.
- **Idempotent ingestion**: one-time commissions (signup/trial/first
  subscription) are deduped per referred user; renewals deduped per
  user-month. Meridian can safely retry webhooks.

## Scaling notes

- The API is **stateless** — JWT auth, no server sessions, no local files —
  so Azure Functions scales instances horizontally on demand; sqlite is only
  a dev convenience, production uses Azure Database for PostgreSQL
  (add PgBouncer / `pool_pre_ping` is already on).
- Webhook ingestion is the hot path: one indexed slug lookup + a handful of
  inserts; outbound callbacks run post-response via `BackgroundTasks`. At
  higher volumes, swap `send_deliveries` for an Azure Storage Queue +
  queue-triggered function (same `function_app.py` can host it) without
  touching the domain.
- Monthly payout runs are O(submitted invoices) and idempotent; they can be
  moved to a timer-triggered function for automation.
