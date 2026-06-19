# Personal Finance Tracker — Project Plan & Architecture

A self-hosted, Finanzguru-style web app: connect your bank account(s) and your own
projects (trading bot, betting model), see every balance in one place, track regular and
irregular spending, and understand your cashflow and net worth. Single-user first,
multi-user later.

> **Not financial or legal advice.** This handles highly sensitive financial data and
> personal banking access — the security and privacy sections are not optional.

---

## 0. Decisions locked in

- **Form factor:** Web app, single-user (just you) first; designed so multi-user can be
  added later without a rewrite.
- **Bank connection:** Use a **licensed aggregation provider** (don't build your own bank
  access). Primary recommendation: **GoCardless Bank Account Data** (formerly Nordigen) —
  it has a genuinely free tier and covers German banks. **FinTS/HBCI** is a no-third-party
  DIY alternative. Details in §2.
- **Your own projects** (trading bot, thesharpbook.com) connect through the **same generic
  "Account Connector" interface** as banks — exactly the pluggable pattern from the trading
  bot plan.
- **Stack:** Python + FastAPI backend, React dashboard, Postgres — consistent with the
  trading bot so you reuse skills and infra.

---

## 1. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | **Python 3.12 + FastAPI** | matches the trading bot; good for any ML categorization |
| Bank aggregation | **GoCardless Bank Account Data** (free tier) | German bank coverage, PSD2-compliant |
| Bank alt (DIY) | `python-fints` (FinTS/HBCI) | direct to many German banks, no third party |
| Storage | **PostgreSQL** | accounts, transactions, categories, snapshots |
| Token/secret encryption | `cryptography` (Fernet) + secret manager | encrypt access tokens at rest |
| Frontend | **React + Vite**, Recharts | charts for cashflow / net worth / categories |
| Jobs / sync | APScheduler or a small worker | periodic balance + transaction sync |
| Orchestration | Docker Compose | api + db + frontend (+ worker) |
| Auth (multi-user later) | Authentik / Keycloak / Auth.js | not needed for single-user v1 |

---

## 2. The hard part: connecting a German bank account

In the EU, third parties can't just log into your bank. Access goes through **PSD2 Open
Banking**, and the party calling the bank API must be a licensed **AISP** (Account
Information Service Provider). **You do not want to become an AISP** — that's a BaFin
licensing process. Instead, use a provider that already holds the license:

### Recommended: GoCardless Bank Account Data (ex-Nordigen)
- Free tier suitable for personal use (**verify current limits/coverage yourself** —
  these change).
- Flow: you create a "requisition" → user is redirected to their bank to authenticate
  (SCA) → you get a token → you pull **balances** and **transactions** (typically up to
  ~24 months of history, bank-dependent).
- **PSD2 reality to design around:** consent expires and requires re-authentication
  roughly **every 90 days** (Strong Customer Authentication). Build a re-consent flow and
  surface "connection expiring" in the UI. Don't assume a connection lasts forever.

### Alternative: FinTS / HBCI (no third party)
- The older German banking protocol many banks still support. `python-fints` can pull
  balances and transactions directly using your online-banking credentials + a TAN.
- Pro: no third-party aggregator, fully self-contained. Con: coverage and reliability vary
  by bank, TAN/2FA handling is fiddly, and it's more brittle. Good fallback or for banks
  the aggregator doesn't cover well.

### Other providers (mostly paid)
Tink (Visa), finAPI (German, used by many local fintechs), Plaid (stronger in US/UK).
Worth knowing, but GoCardless free tier is the right starting point for a personal app.

> **Design implication:** Put bank access behind an interface so you can swap GoCardless ↔
> FinTS ↔ anything without touching the rest of the app.

---

## 3. Architecture

```
                    ┌──────────────────────────────────────────────┐
                    │            Finance Tracker (Python)            │
                    │                                                │
   Bank (PSD2) ───► │  Account Connectors ──► Sync Engine            │
   GoCardless/FinTS │   (Bank, TradingBot,        │                  │
                    │    Sharpbook, Manual)       ▼                  │
   Trading bot ───► │        │            Normalized Transactions    │
   (your API)       │        │            + Balances                 │
                    │        │                 │                     │
   Sharpbook  ────► │        │                 ▼                     │
   (adapter)        │        │         Categorization Engine         │
                    │        │         (rules + recurring + ML?)     │
                    │        ▼                 │                     │
                    │   Persistence  ◄─────────┘                     │
                    │   (Postgres)        Net Worth Aggregator       │
                    └──────────┬────────────────────┬───────────────┘
                               │                    │
                               ▼                    ▼
                         FastAPI + REST ──► React Dashboard
```

---

## 4. Components

### 4.1 Account Connector interface (the core abstraction)
Everything that has a balance or transactions implements one interface:

```python
class AccountConnector(Protocol):
    def list_accounts(self) -> list[Account]: ...
    def get_balance(self, account_id: str) -> Balance: ...
    def get_transactions(self, account_id: str, since: date) -> list[Transaction]: ...
```

Implementations:
- `BankConnector` (GoCardless) / `FinTSConnector` — banks.
- `TradingBotConnector` — calls the trading bot's API (you'll add a small read-only
  `/balance` + `/equity` endpoint to it; the bot already stores this data).
- `SharpbookConnector` — thesharpbook.com has no documented public API, so: check for one;
  if none, build a session-based fetch/scraper, or fall back to **manual entry**.
- `ManualConnector` — for anything with no API (cash, a friend's IOU, etc.).

This is the same pluggable pattern as the trading bot's `Broker` — reuse the mental model.

### 4.2 Sync engine
- Scheduled jobs pull balances + new transactions per connector.
- Idempotent upserts (dedupe by a stable transaction hash/id).
- Tracks last-sync time and surfaces failures + expiring consents.

### 4.3 Categorization engine (regular + irregular spending)
This is the Finanzguru magic. Build it in layers:
- **Rules first:** match payee/merchant strings → category (rent, internet, mobile,
  groceries, salary, etc.). Fast, transparent, easy to correct.
- **User overrides:** let yourself reclassify a transaction; remember the rule.
- **ML later (optional):** train a classifier on your corrected data once you have enough.
- Categories are a small editable taxonomy with income vs expense and fixed vs variable
  flags (so you can separate your "regular" bills from "irregular" groceries).

### 4.4 Recurring / subscription detection
Detect transactions that repeat (similar payee + amount + monthly-ish cadence) → mark as
recurring, forecast next occurrence, list upcoming bills. This is what powers the
"contracts/subscriptions" view Finanzguru is known for.

### 4.5 Net worth aggregator
Sum balances across **all** connectors (banks + trading bot + betting + manual) into one
net-worth figure, snapshotted over time for the trend chart.

---

## 5. Data model (Postgres, sketch)

- `accounts(id, connector, type, name, currency, institution)`
- `balances(account_id, ts, amount)` — time-series for net-worth history
- `transactions(id, account_id, ts, amount, currency, raw_payee, description, category_id, is_recurring, hash)`
- `categories(id, name, kind[income|expense], is_fixed)`
- `rules(id, match_pattern, category_id, priority)` — categorization rules + your overrides
- `recurring(id, payee, amount_est, cadence, next_due, account_id)`
- `connections(id, connector, status, consent_expires_at)` — track the 90-day re-consent
- `net_worth_snapshots(ts, total, breakdown_json)`

---

## 6. Dashboard spec

- **Net worth:** headline total + trend chart across all accounts.
- **Accounts overview:** every balance in one list (banks, trading bot, betting, manual),
  with sync status + "consent expiring" warnings.
- **Cashflow:** monthly inflows vs outflows; income (salary + project withdrawals) vs spend.
- **Category breakdown:** spending by category, fixed vs variable split.
- **Upcoming bills / recurring:** detected subscriptions and their next due dates.
- **Transactions:** searchable/filterable list with inline recategorization.
- **Budget (later):** set per-category limits and track against them.

---

## 7. Connecting your own projects

- **Trading bot:** add a small read-only authenticated endpoint to it (e.g.
  `GET /api/balance` returning equity + cash). The bot already persists this — you're just
  exposing it. The tracker's `TradingBotConnector` consumes it. Use a shared secret/API key.
- **thesharpbook.com:** no public API found. Order of preference: (1) use an official API
  if one exists, (2) authenticated scrape of your own account page, (3) manual entry. Keep
  it behind `SharpbookConnector` so the rest of the app doesn't care which.
- **Pattern:** any future project just needs to implement `AccountConnector`.

---

## 8. Security & privacy (do not skip — this is your bank data)

- **Encrypt access tokens / credentials at rest** (Fernet or DB-level encryption); never
  store them in plaintext or commit them.
- Secrets via environment / a secret manager, never in the repo.
- Prefer **read-only / information-only** bank access (AIS), never payment-initiation.
- Lock the app down: it's exposed nothing publicly in v1; if you host it, put it behind
  auth + HTTPS + ideally a VPN/tailnet, not the open internet.
- Minimize what you store; have a way to purge a connection and its data.
- Keep an eye on dependency security — this app is a high-value target.

---

## 9. Multi-user later (family & friends)

When you open it up, several things become real obligations, not nice-to-haves:
- **Auth + strict per-user data isolation** (every query scoped to a user; encrypted
  per-user secrets).
- **GDPR:** you'd be processing other people's financial data — consent, data export, the
  right to deletion, a privacy policy, and a clear data-retention story.
- **Aggregator terms:** free tiers (GoCardless etc.) are often scoped to personal use or
  limited end-user counts. **Re-read the provider's terms before onboarding others** —
  redistributing access may exceed the free tier or require a commercial agreement.
- Treat "share with friends" as a deliberate milestone with its own checklist, not a flag
  you flip.

---

## 10. Build vs adopt (worth a look first)

Mature open-source self-hosted finance apps already exist and handle a lot of this:
**Firefly III** (popular, has importers), **Actual Budget**, **Maybe Finance**. Even if you
build your own, skimming how they model transactions, categorization, and bank import will
save you time — and you could fork/self-host one as a faster path to "free Finanzguru" if
the goal is the result more than the build. Your call; building from scratch is the better
learning project.

---

## 11. Phased roadmap

- **Phase 0 — Scaffold.** FastAPI + Postgres + Docker Compose, config/secrets with token
  encryption, the `AccountConnector` interface, and a `ManualConnector` so you can add
  balances by hand end-to-end.
- **Phase 1 — Bank connection.** Integrate GoCardless Bank Account Data: requisition/consent
  flow, pull balances + transactions, store them, handle the 90-day re-consent.
- **Phase 2 — Categorization + recurring.** Rules engine, manual overrides, recurring
  detection, the category taxonomy.
- **Phase 3 — Dashboard.** React app: net worth, accounts, cashflow, categories, recurring,
  transactions with inline recategorization.
- **Phase 4 — Your projects.** Add `/balance` to the trading bot + `TradingBotConnector`;
  build `SharpbookConnector` (API/scrape/manual).
- **Phase 5 — Polish.** Budgets, forecasting, alerts, sync reliability, FinTS fallback.
- **Phase 6 — Multi-user (later).** Auth, per-user isolation, GDPR, re-check aggregator
  terms (§9) before onboarding anyone.

---

## 12. Suggested repo structure

```
finance-tracker/
├── docker-compose.yml
├── backend/
│   ├── connectors/    # AccountConnector + Bank/FinTS/TradingBot/Sharpbook/Manual
│   ├── sync/          # scheduled sync engine, dedupe, consent tracking
│   ├── categorize/    # rules, overrides, recurring detection, (ml later)
│   ├── networth/      # aggregation + snapshots
│   ├── persistence/   # db models, repositories, token encryption
│   └── api/           # FastAPI routes
├── frontend/          # React + Vite
├── config/
└── tests/
```

---

## 13. First task for Claude Code

Paste something like this to kick off:

> Set up Phase 0 of the plan in `finance-tracker/`: Python 3.12 + FastAPI, Docker Compose
> with Postgres, pydantic-settings config, SQLAlchemy models for the §5 schema, and
> Fernet-based encryption for any stored access tokens. Define the `AccountConnector`
> protocol from §4.1 and implement a `ManualConnector` plus REST endpoints to add accounts
> and balances by hand, so I can see a net-worth total end-to-end. Add pytest. Don't
> integrate any real bank yet — just the scaffold, manual connector, and net-worth
> aggregation.

Then do Phase 1 (GoCardless) next, keeping every data source behind `AccountConnector`.
