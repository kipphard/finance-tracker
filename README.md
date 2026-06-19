# Finance Tracker

Self-hosted, Finanzguru-style personal finance tracker. See [`docs/plan.md`](docs/plan.md).

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

API at <http://localhost:8000>, interactive docs at <http://localhost:8000/docs>.

> If port 8000 is already in use, set `API_PORT=8001` (or any free port) in `.env` and
> use that port in the URLs below.

## End-to-end net-worth walkthrough

```bash
# Add two accounts
curl -s -X POST localhost:8000/accounts -H 'content-type: application/json' \
  -d '{"type":"checking","name":"Giro","currency":"EUR"}'
curl -s -X POST localhost:8000/accounts -H 'content-type: application/json' \
  -d '{"type":"cash","name":"Wallet","currency":"EUR"}'

# Add a balance to each (use the ids returned above)
curl -s -X POST localhost:8000/accounts/<ID1>/balances -H 'content-type: application/json' \
  -d '{"amount":"1000.00"}'
curl -s -X POST localhost:8000/accounts/<ID2>/balances -H 'content-type: application/json' \
  -d '{"amount":"250.50"}'

# Net worth: headline total + per-account breakdown + by-currency
curl -s localhost:8000/networth

# Snapshot it for the trend chart, then list snapshots
curl -s -X POST localhost:8000/networth/snapshots
curl -s localhost:8000/networth/snapshots
```

## Manual cashflow (recurring inflows / outflows)

Add recurring income and expenses by hand and get a monthly inflow/outflow/net summary.
Cadences: `weekly`, `biweekly`, `monthly`, `quarterly`, `yearly`, `one_off` (one-offs are
excluded from the recurring monthly total). These are budget projections and do **not**
affect net worth.

```bash
# Add an inflow and some outflows
curl -s -X POST localhost:8000/cashflow -H 'content-type: application/json' \
  -d '{"direction":"inflow","name":"Salary","amount":"3000","cadence":"monthly"}'
curl -s -X POST localhost:8000/cashflow -H 'content-type: application/json' \
  -d '{"direction":"outflow","name":"Rent","amount":"1200","cadence":"monthly"}'
curl -s -X POST localhost:8000/cashflow -H 'content-type: application/json' \
  -d '{"direction":"outflow","name":"Insurance","amount":"1200","cadence":"yearly"}'

# Monthly summary: inflow / outflow / net (everything normalized to a monthly figure)
curl -s localhost:8000/cashflow/summary
# -> {"currency":"EUR","monthly_inflow":"3000.00","monthly_outflow":"1300.00","monthly_net":"1700.00","item_count":3}

# List / edit / remove
curl -s localhost:8000/cashflow
curl -s -X PATCH localhost:8000/cashflow/<ID> -d '{"active":false}' -H 'content-type: application/json'
curl -s -X DELETE localhost:8000/cashflow/<ID>
```

## Roadmap

- **Activate bank linking when GoCardless reopens signups.** The connector, consent flow,
  sync engine, and `/banks/*` endpoints are already built and tested (see
  `backend/connectors/gocardless/`, `backend/sync/`, `tests/test_bank_flow.py`). To go
  live: register at <https://bankaccountdata.gocardless.com/> → User Secrets, put the
  `secret_id`/`secret_key` into `.env` as `GOCARDLESS_SECRET_ID`/`GOCARDLESS_SECRET_KEY`,
  restart, then `POST /banks/requisitions` → consent → `POST /banks/requisitions/{id}/finalize`
  → `POST /banks/connections/{id}/sync`. As of 2026-06-19, signups are disabled.
- Phase 2: categorization + recurring detection. Phase 3: React dashboard.

## Security notes (§8)

- Access tokens are encrypted at rest with Fernet (`EncryptedString` column type). The
  mechanism is wired onto `connections.access_token` / `refresh_token` already.
- Secrets come from the environment / `.env` only — `.env` is gitignored; never commit it.
- No FX conversion in Phase 0: the net-worth `total` sums balances in `APP_BASE_CURRENCY`;
  other currencies are reported separately under `by_currency`.
