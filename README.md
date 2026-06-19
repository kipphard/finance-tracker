# Finance Tracker — Phase 0 Scaffold

Self-hosted, Finanzguru-style personal finance tracker. This is **Phase 0** of
[`docs/plan.md`](docs/plan.md): the scaffold, the
`AccountConnector` abstraction (§4.1), a `ManualConnector`, and end-to-end net-worth
aggregation (§4.5). **No real bank integration yet** — that's Phase 1.

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

## Security notes (§8)

- Access tokens are encrypted at rest with Fernet (`EncryptedString` column type). The
  mechanism is wired onto `connections.access_token` / `refresh_token` already.
- Secrets come from the environment / `.env` only — `.env` is gitignored; never commit it.
- No FX conversion in Phase 0: the net-worth `total` sums balances in `APP_BASE_CURRENCY`;
  other currencies are reported separately under `by_currency`.
