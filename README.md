# Finance Tracker

Self-hosted web app — a **personal finance tracker** and a **freelance time-tracking &
invoicing** tool. The left sidebar switches between **💰 Finances** (act), **📈 Analytics**
(charts/trends), **🧑‍💻 Freelance**, **🧭 Playbook**, and **⚙️ Settings**.

**📖 For a full walkthrough of everything the app does, see [`docs/GUIDE.md`](docs/GUIDE.md).**
Original product plan: [`docs/plan.md`](docs/plan.md).

## Features at a glance

**💰 Finances** — manual accounts + net worth (with a snapshot trend chart); transactions
(manual entry, German-tolerant CSV import, categories + a payee→category rules engine, tags,
receipt attachments, transfers, recurring/series with auto-posting, off-balance flag); planning
(monthly cashflow, per-category budgets, net-worth forecast, allocation buckets, emergency fund,
debts, a planned-purchases wishlist (save €X/mo per item → a "Planned purchases fund" pot in the
leftover split), alerts); reports + a tax-advisor CSV export.

**🧑‍💻 Freelance** — start/stop timer (survives reloads) + manual entries; clients with hour
budgets and projects with per-project rate/budget overrides; invoices built from tracked time
or as a blank flat-fee, with hourly **and** flat (Pauschal) lines, **DE/EN** language,
**Kleinunternehmer §19 / 19% VAT**, due dates + overdue tracking, a scan-to-pay **GiroCode**,
**PDF** download, in-app **email** (Gmail SMTP), and **auto-reconciliation** that marks an
invoice paid from the matching bank transaction (and lists the Zahlungseingang).

**Status**
- **Phase 0 (done):** scaffold, the `AccountConnector` abstraction (§4.1), a
  `ManualConnector`, manual accounts/balances, end-to-end net-worth aggregation (§4.5).
- **Phase 1 — bank linking (built, dormant):** a GoCardless `BankConnector`, consent/
  requisition flow, and sync engine are implemented and tested, but **inactive** because
  GoCardless Bank Account Data new signups are currently disabled, so no API keys can be
  obtained. The `/banks/*` endpoints return `503` until `GOCARDLESS_SECRET_ID`/`KEY` are
  set in `.env`. See "Roadmap" below.
- **Manual cashflow (done):** hand-entered recurring inflows/outflows with a monthly
  summary — the usable stand-in for automatic bank import.
- **Phase 2 — categorization + recurring (done):** category taxonomy, a rules engine
  (payee → category), manual reclassify (optionally remembered as a rule), manual
  transaction entry + **CSV import** of bank statements, and recurring/subscription
  detection.

## Stack

- Python 3.12 + FastAPI (sync SQLAlchemy 2.0)
- PostgreSQL, Alembic migrations
- pydantic-settings for config
- Fernet (`cryptography`) encryption for access tokens at rest
- Docker Compose (db + api)
- pytest (runs on in-memory SQLite — no Docker needed)

## Layout

```
backend/
  config.py            # pydantic-settings
  connectors/          # AccountConnector protocol (base.py) + ManualConnector + registry
  persistence/         # SQLAlchemy models, engine/session, Fernet EncryptedString, repository
  networth/            # net-worth aggregator + snapshots
  api/                 # FastAPI routers (accounts, networth, health)
  alembic/             # migrations
tests/                 # pytest suite
```

## Run the tests (no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Run the app (Docker Compose)

```bash
cp .env.example .env
# Generate a Fernet key and paste it into FERNET_KEY in .env:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

docker compose up --build      # or: docker-compose up --build (legacy v2 binary)
```

API at <http://localhost:8000>, interactive docs at <http://localhost:8000/api/docs>.
All API paths are under `/api` (so the dashboard SPA can own `/`); `/health` stays at root.

> If port 8000 is already in use, set `API_PORT=8001` (or any free port) in `.env` and
> use that port in the URLs below.

## End-to-end net-worth walkthrough

```bash
# Add two accounts
curl -s -X POST localhost:8000/api/accounts -H 'content-type: application/json' \
  -d '{"type":"checking","name":"Giro","currency":"EUR"}'
curl -s -X POST localhost:8000/api/accounts -H 'content-type: application/json' \
  -d '{"type":"cash","name":"Wallet","currency":"EUR"}'

# Add a balance to each (use the ids returned above)
curl -s -X POST localhost:8000/api/accounts/<ID1>/balances -H 'content-type: application/json' \
  -d '{"amount":"1000.00"}'
curl -s -X POST localhost:8000/api/accounts/<ID2>/balances -H 'content-type: application/json' \
  -d '{"amount":"250.50"}'

# Net worth: headline total + per-account breakdown + by-currency
curl -s localhost:8000/api/networth

# Snapshot it for the trend chart, then list snapshots
curl -s -X POST localhost:8000/api/networth/snapshots
curl -s localhost:8000/api/networth/snapshots
```

## Manual cashflow (recurring inflows / outflows)

Add recurring income and expenses by hand and get a monthly inflow/outflow/net summary.
Cadences: `weekly`, `biweekly`, `monthly`, `quarterly`, `yearly`, `one_off` (one-offs are
excluded from the recurring monthly total). These are budget projections and do **not**
affect net worth.

```bash
# Add an inflow and some outflows
curl -s -X POST localhost:8000/api/cashflow -H 'content-type: application/json' \
  -d '{"direction":"inflow","name":"Salary","amount":"3000","cadence":"monthly"}'
curl -s -X POST localhost:8000/api/cashflow -H 'content-type: application/json' \
  -d '{"direction":"outflow","name":"Rent","amount":"1200","cadence":"monthly"}'
curl -s -X POST localhost:8000/api/cashflow -H 'content-type: application/json' \
  -d '{"direction":"outflow","name":"Insurance","amount":"1200","cadence":"yearly"}'

# Monthly summary: inflow / outflow / net (everything normalized to a monthly figure)
curl -s localhost:8000/api/cashflow/summary
# -> {"currency":"EUR","monthly_inflow":"3000.00","monthly_outflow":"1300.00","monthly_net":"1700.00","item_count":3}

# List / edit / remove
curl -s localhost:8000/api/cashflow
curl -s -X PATCH localhost:8000/api/cashflow/<ID> -d '{"active":false}' -H 'content-type: application/json'
curl -s -X DELETE localhost:8000/api/cashflow/<ID>
```

## Categorization, transactions & recurring (Phase 2)

```bash
# Seed a starter category taxonomy, then add a rule (payee substring -> category)
curl -s -X POST localhost:8000/api/categories/seed
GROC=<id of "Groceries" from GET /categories>
curl -s -X POST localhost:8000/api/rules -H 'content-type: application/json' \
  -d "{\"match_pattern\":\"rewe\",\"category_id\":\"$GROC\"}"

# Log a transaction by hand (auto-categorized by the rules)
curl -s -X POST localhost:8000/api/accounts/<ACCOUNT_ID>/transactions \
  -H 'content-type: application/json' \
  -d '{"ts":"2026-03-01T00:00:00Z","amount":"-23.50","raw_payee":"REWE Markt"}'

# Bulk-import a bank statement CSV (tolerant of ;-delimited, DD.MM.YYYY, "1.234,56")
curl -s -X POST localhost:8000/api/accounts/<ACCOUNT_ID>/transactions/import \
  -F "file=@statement.csv;type=text/csv"

# Reclassify a transaction and remember it as a rule for next time
curl -s -X PATCH localhost:8000/api/transactions/<TXN_ID> -H 'content-type: application/json' \
  -d '{"category_id":"<CAT_ID>","remember":true}'

# Re-run rules over existing transactions; list uncategorized
curl -s -X POST localhost:8000/api/transactions/categorize
curl -s "localhost:8000/api/transactions?uncategorized=true"

# Detect recurring subscriptions (repeating payee + amount + monthly-ish cadence)
curl -s -X POST localhost:8000/api/recurring/detect
curl -s localhost:8000/api/recurring
```

CSV columns are matched case-insensitively against common English/German aliases
(`date`/`datum`/`buchungstag`, `amount`/`betrag`, `payee`/`name`, `description`/
`verwendungszweck`); a date and an amount column are required. Re-importing the same file
is idempotent (deduped by a content hash). Transactions are for spending analysis and do
**not** affect net worth (which is still balance-based).

## Roadmap

- **Activate bank linking when GoCardless reopens signups.** The connector, consent flow,
  sync engine, and `/banks/*` endpoints are already built and tested (see
  `backend/connectors/gocardless/`, `backend/sync/`, `tests/test_bank_flow.py`). To go
  live: register at <https://bankaccountdata.gocardless.com/> → User Secrets, put the
  `secret_id`/`secret_key` into `.env` as `GOCARDLESS_SECRET_ID`/`GOCARDLESS_SECRET_KEY`,
  restart, then `POST /banks/requisitions` → consent → `POST /banks/requisitions/{id}/finalize`
  → `POST /banks/connections/{id}/sync`. As of 2026-06-19, signups are disabled.
- Phase 3: React dashboard (net worth, accounts, cashflow, category breakdown, recurring,
  transactions with inline recategorization).

## Frontend (dashboard, Phase 3)

React + Vite + TypeScript + SCSS with Recharts, in `frontend/`. Shows net worth + trend,
accounts, monthly cashflow, spending by category (fixed vs variable), recurring/upcoming
bills, and a searchable transaction list with **inline recategorization**.

```bash
cd frontend
npm install
# Run the backend first (any local port), then point the Vite dev proxy at it:
VITE_API_TARGET=http://127.0.0.1:8000 npm run dev   # http://localhost:5173

npm run build    # production build -> frontend/dist (served by nginx in prod)
```

The SPA calls the API same-origin at `/api`; in dev, Vite proxies `/api` and `/health` to
the backend target.

## Deployment (production)

Runs at **https://finance-tracker.kipphard.com** on the Hetzner box, **not** in Docker —
it follows the host's pattern: a **systemd** service running `uvicorn` on `127.0.0.1:8002`
behind nginx, against the host's **system PostgreSQL** (a dedicated `finance` role + DB).

- **Service:** `/etc/systemd/system/finance-tracker.service` (runs `alembic upgrade head`
  as `ExecStartPre`, then uvicorn). Code in `/opt/finance-tracker`; secrets in
  `/opt/finance-tracker/.env` (chmod 600, server-only — never committed).
- **nginx vhost:** `finance-tracker.kipphard.com` → `127.0.0.1:8002`, reusing the shared
  `*.kipphard.com` Cloudflare origin cert (no per-vhost `real_ip_header`).
- **Push-to-deploy:** `.github/workflows/deploy.yml` rsyncs to the server and restarts the
  service on push to `main`. Needs repo secret `DEPLOY_SSH_KEY`; GitHub Actions billing
  must be active. First deploy was done manually via rsync/SSH.
- **Dev model:** edit + test locally (`pytest`, `docker compose up` for a local stack) →
  push → it deploys to and runs on the server (the single live instance). Development and
  tests still happen locally; only the running app lives on the server.

## Security notes (§8)

- Access tokens are encrypted at rest with Fernet (`EncryptedString` column type). The
  mechanism is wired onto `connections.access_token` / `refresh_token` already.
- Secrets come from the environment / `.env` only — `.env` is gitignored; never commit it.
- No FX conversion in Phase 0: the net-worth `total` sums balances in `APP_BASE_CURRENCY`;
  other currencies are reported separately under `by_currency`.
