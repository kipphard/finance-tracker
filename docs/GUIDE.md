# Finance Tracker — Full Guide

A self-hosted, single-user web app with **two sides**, switched via the left sidebar:

- **💰 Finances** — a personal finance tracker (net worth, transactions, budgets, forecasts).
- **🧑‍💻 Freelance** — time tracking, clients/projects, and German-style invoicing.

Live at <https://finance-tracker.kipphard.com>. Log in (register an account), and everything
below is scoped to you. There's a **demo account** (`akipphard@yahoo.de`) pre-filled with
example data for every feature.

---

## 💰 Finances

The Finances dashboard is a grid of cards you can **drag to reorder**; a 🌙/☀️ **dark-mode**
toggle lives in the sidebar.

### Accounts & net worth
- Add **accounts** (checking, cash, savings, brokerage, …). Net worth = the sum of each
  manual account's transactions (bank-synced accounts would use their latest balance).
- A **net-worth hero** with the headline total + a **trend chart** from daily snapshots
  (auto-snapshotted nightly; you can also "Take snapshot" manually).
- Brokerage accounts can carry an **expected return** that feeds the forecast.

### Transactions
- **Add transactions** by hand (account · date · amount · payee), or **import a bank CSV**
  (tolerant of `;`-delimited, `DD.MM.YYYY` dates, `1.234,56` amounts; idempotent/deduped).
- **Categories + a rules engine**: payee → category auto-matching; reclassify a transaction
  and optionally **remember it as a rule**. Seedable starter taxonomy.
- **Tags**, free-text **description**, and **counterparty / invoice number / VAT rate** for
  accounting (the invoice-number field is what links a payment to a freelance invoice).
- **Attachments**: PDF/image **receipts** on a transaction.
- **Transfers** between accounts (excluded from income/expense reports).
- **Recurring transactions**: tick "Repeat" to create a template; due occurrences are
  auto-posted with catch-up + dedupe. A "Scheduled" card lists upcoming ones with a
  **due-soon** badge; recurring/backfilled entries can be linked as a **series** and edited
  together or one-by-one.
- **Off-balance** flag for record-only entries (e.g. freelance income tracked for tax) —
  kept in lists/reports but excluded from net worth and the forecast.

### Planning & insight cards
- **Monthly cashflow** — planned recurring inflows/outflows + a monthly net summary; can be
  **materialized** into real dated transactions.
- **Budgets** — per-category monthly limits with spend-vs-limit progress bars.
- **Forecast** — net worth projected from your average monthly net + account returns.
- **Cash runway** — how many months your **liquid** (non-investment) balance lasts at the current
  monthly net ("∞" when you're net-positive). The freelancer's most important number.
- **Allocation** — split the monthly leftover (income − fixed) into buckets (Savings/Invest/…).
- **Emergency fund** — a target of N× monthly fixed costs and how funded you are.
- **Debts / "to pay off"** — one-off obligations; overdue ones surface in Alerts.
- **Alerts** — over-budget categories, bills due soon, etc.
- **Reports** — actual monthly in/out, income vs expense, and a **CSV export** for your tax
  advisor.

---

## 🧑‍💻 Freelance

Four tabs: **Time · Clients · Invoices · Settings**.

### Time tracking
- A big **start/stop timer** against a client (and optional project). The running entry lives
  server-side, so it **survives a page reload**. Type what you're working on; saved on stop.
- **Manual entries** (`+ Manual entry`) for after-the-fact logging: client, project, start
  time, duration, description.
- A filterable **time-entries table** (by client / project), with edit/delete. Billed entries
  are locked and show a **billed** badge.

### Clients
- Per-client **hourly rate**, optional **hour budget (Kontingent)** with a usage bar, invoice
  address, email, notes, archive.
- Each client card shows **tracked / unbilled hours / unbilled €** and a one-click
  **Create invoice**.

### Projects (under a client)
- Optional **rate and budget overrides** per project (blank = inherit the client's).
- Each project shows its own tracked/unbilled figures, a **budget bar**, and its own
  **Invoice** action. Time entries and invoices can be scoped to a project.

### Invoices
- **Create from tracked time**: pick a client (+ optional project), tick exactly which
  **unbilled entries** to bill (or narrow by date range) — with a running total.
- **Blank invoice**: start empty to bill a **flat project/service fee** with no tracked time.
- **Recurring / retainers**: a "Recurring invoices" panel where you set a client (+ project) on
  a schedule (weekly … yearly) that **auto-drafts an invoice each period** — either a **flat fee
  (Pauschale)** or **that period's tracked time**. Drafts are generated when you open the Invoices
  tab (catch-up + advance); you review and send them. Pause/resume or delete a retainer anytime.
- **Line items**: mix **hourly** lines (Hours × Rate) and **flat / Pauschal** lines (just an
  Amount, no hours). Edit descriptions/amounts; total updates live. A **✨ Tidy** button does a
  rule-based cleanup (no AI): strips URLs / internal "(siehe …)" notes / list markers, dedupes
  repeated phrases, capitalizes, and **merges duplicate lines** (same description + rate → summed
  hours/amount). Review the result, then **Save lines**.
- **Language DE / EN** — switches all PDF labels, the date format, the greeting, and the §19
  note; switching language re-translates the boilerplate intro (your custom text is kept).
- **Kleinunternehmer (§19 UStG)** — no VAT + the §19 note. Untick it in Settings and invoices
  add **19% VAT** (net → gross, broken out on the PDF).
- **Due dates** — auto-set from your payment term (e.g. 14 days); shown on the PDF and list,
  with an **überfällig** (overdue) badge once past due and unpaid.
- **Mahnwesen (payment reminders)** — for a sent/overdue invoice, a **⏰ Zahlungserinnerung →
  1./2./3. Mahnung** button emails an escalating German/English reminder (with the invoice PDF
  attached) and tracks the **Mahnstufe** ("1. Mahnung gesendet am …").
- **GiroCode** — a scan-to-pay **EPC-QR** on the PDF that pre-fills a SEPA transfer (your IBAN,
  amount, invoice no. as Verwendungszweck). Plus a free-text **payment info/link** line
  (e.g. a Revolut/PayPal link) from Settings.
- **Gesamtstunden** — total billed hours printed above the amount.
- **Download PDF** (reportlab, German Kleinunternehmer layout) or **✉ Email** it directly from
  the app (server-side via your Gmail SMTP) — sending flips the status to **sent** and attaches
  the PDF.
- **Delete** an invoice → its time entries go back to unbilled.

### Getting paid (invoice ↔ transactions)
- Record the incoming bank transaction in **Finances** with the **invoice number** in its
  Invoice-number field. The invoice then:
  - **auto-marks paid** — but only when matching transactions **cover the full total**
    (partial payments show *"€X von €Y erhalten"*; refunds/wrong amounts never flip it; a
    manual "paid" is never auto-undone);
  - shows a **Zahlungseingang** list (which transaction(s) paid it, with date/account/amount).
- The transactions table shows a **`#100001 · paid`** badge next to a matched invoice number.

### Insights
A dedicated tab with:
- **Client profitability** — per client: **effective €/h** (total invoiced ÷ tracked hours,
  flat fees included), tracked/billed/unbilled hours, and invoiced vs. paid totals — sorted by
  the best effective rate, so you can see which clients are actually worth it.
- **Project budgets — burn-down** — for every project with an hour budget (Kontingent): a bar of
  tracked vs. budget, hours remaining, and an **über Budget** flag once you've blown past it.

### Settings (your business profile)
Everything the invoice pulls from: name, company, phone, email, **street / Postleitzahl /
city**, **IBAN / BIC / tax number**, the **Kleinunternehmer/VAT** toggle, **payment term
(days)** + **payment info/link**, **default language**, **default hourly rate**, **next invoice
number**, and optional overrides for the §19 note and intro text. Plus a **Notification digest**:
choose **Off / Weekly / Monthly**, tick which sections to include (**Invoices / Time / Finance**),
and **Send test digest now** to preview it — emailed via your Gmail SMTP.

## Cross-app niceties
- **⌘K command palette** — press ⌘K (Ctrl+K) anywhere to jump to any section or toggle the theme.
- **Idle detection** — if the timer runs 15 min without activity, it asks whether you're still working.
- **Installable (PWA)** — "Add to Home Screen" on mobile/desktop for an app-like, fullscreen launch;
  the shell works offline after first load. (The site is also just responsive in any browser.)

---

## Accounts, privacy & ops
- **Auth**: register/login (JWT); strict **per-user isolation** on every record.
- **GDPR**: `GET /api/me/export` (your data) and `DELETE /api/me` (erase).
- **API docs**: <https://finance-tracker.kipphard.com/api/docs>.
- **Deployment & dev workflow**: see the [README](../README.md).

## Roadmap / ideas
Tracked as **GitHub issues** (`freelance` / `finance` / `idea` labels):
<https://github.com/kipphard/finance-tracker/issues> — e.g. Mahnwesen reminders, recurring
retainer invoices, AI line-item summaries, notification emails, bank sync, profitability &
runway analytics, project burn-down, command palette, PWA.
