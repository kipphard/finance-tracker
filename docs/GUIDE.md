# Finance Tracker — Full Guide

A self-hosted, single-user web app. The left sidebar switches between two areas:

- **💰 Finances** — personal finance, with three sub-tabs:
  - **Overview** — the money cockpit: things you *act on* (net worth, accounts, runway, the leftover
    split, planned purchases, emergency fund, debts, budgets, alerts, transactions).
  - **Analytics** — read-only charts & breakdowns you look at to understand *trends* (net-worth
    forecast, 12-month cashflow, income vs expense, spending by category, detected subscriptions).
  - **Settings** — app configuration (transaction categories) plus the **money playbook**.
- **🧑‍💻 Business** — time tracking, clients/projects, and German-style invoicing.

Live at <https://finance-tracker.kipphard.com>. Log in (register an account), and everything
below is scoped to you. There's a **demo account** (`akipphard@yahoo.de`) pre-filled with
example data for every feature.

---

## 💰 Finances

Finances has three sub-tabs — **Overview · Analytics · Settings**. The **Overview** (below) and
**Analytics** are each a **masonry grid** of cards you can **drag to reorder** (short cards rise to
fill empty space, so there are no big gaps), and each keeps its own order. A 🌙/☀️ **dark-mode**
toggle lives in the sidebar.

#### Overview

### Accounts & net worth
- Add **accounts** (checking, cash, savings, brokerage, …). Net worth = the sum of each
  manual account's transactions (bank-synced accounts would use their latest balance).
- A **net-worth hero** with the headline total + a **trend chart** from daily snapshots
  (auto-snapshotted nightly; you can also "Take snapshot" manually).
- Brokerage accounts can carry an **expected return** that feeds the forecast.
- **Reconcile** (⚖ on an account row) — because a manual account's balance is the *sum of its
  transactions*, it can drift from the real bank balance over time (a forgotten cash spend, an
  import miss). Assert the **real balance on a date**; the app shows the discrepancy vs the
  computed balance and books **one labelled "Balance reconciliation" entry** for the difference so
  the balance matches reality going forward. That entry is an internal `is_transfer` adjustment —
  **excluded from income/expense and the EÜR**, but counted in the balance — and each reconcile is
  kept as a per-account history. (Editing an account no longer has a balance field; use Reconcile.)

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

### Planning & action cards
- **Cash runway** — how many months your **liquid** (non-investment) balance lasts at the current
  monthly net ("∞" when you're net-positive). The freelancer's most important number. Money in a
  **tax-reserve account** (see *Steuerrücklage* below) is always **earmarked and excluded** from this
  liquid pool — so the Finanzamt's share never inflates your runway. Each other goal account can be
  earmarked too via an **"exclude from runway"** toggle: a linked **emergency fund** is excluded by
  default (it's money you've set aside — flip it off if you'd rather count it as survival runway),
  and any linked **%-bucket** (e.g. a Savings → Tagesgeld) can be opted in.
- **Sustainable monthly pay** — the freelancer's "how much can I pay myself this month?" number.
  Takes your trailing **average monthly net** (the same figure runway/forecast use, so fixed costs
  are already baked in), subtracts the recommended **tax-reserve** set-aside and any **planned
  savings**, and then **caps the result at your liquid balance** so it never suggests paying out
  cash you don't have. Turns lumpy freelance income into one steady figure. A guide, not advice.
- **Distribute leftover (Allocation)** — split the monthly leftover (income − fixed) into buckets
  (Savings/Invest/Fun). These are taken *off the top* in order: **Debt** first, then the
  **Emergency fund** cut from what's left after debt (its % applies to *leftover − debt*), then
  **Planned purchases** and the **Steuerrücklage**; everything else splits what remains.
  **Link a real account** to any %-bucket, the emergency fund, or a planned-purchase item, then hit
  **Apply this month**: it books the moves — a **transfer** from your chosen source account into each
  linked bucket / fund, and an **expense** out of the source for each ticked debt (cleared debts are
  marked paid). You preview and confirm the list first, and it **remembers when you last applied** —
  if you've already run it this month it warns you before booking duplicates.
- **Planned purchases** — a wishlist (e.g. *Nintendo Switch 2 · €499*, *Urlaub · €1000*). Give each
  item a **save €X/month** and it tells you when you'll have saved enough ("in ~5 months · by Nov
  2026"). The sum of those monthly saves becomes a **"Planned purchases fund"** pot that shows up in
  the **Distribute leftover** card *off the top* (alongside Debt and Emergency fund) — so deciding to
  save for something visibly shrinks what's left to split between Savings / Invest / Fun, instead of
  pretending the money appears from nowhere. Just add an item + price, then set a monthly amount.
  **Link a savings account** to an item and *Apply this month* transfers its monthly save into it; tick
  the 🔒 to also keep that balance out of your cash runway.
- **Emergency fund** — a target of N× monthly fixed costs and how funded you are. **Link an account**
  and "saved so far" follows its live balance (like the Steuerrücklage); *Apply this month* then pays
  the contribution into it. If **one account backs two goals** (e.g. the same Tagesgeld is both your
  emergency fund *and* your Steuerrücklage), set a **fill order** on each — the lower number fills
  first up to its target, the other gets the remainder, so the same euros aren't counted twice.
- **Steuerrücklage (tax reserve)** — the freelancer's safety net against an end-of-year tax
  shock. It reuses the **§32a EÜR engine** to estimate the income tax your freelance profit has
  added *so far this year* (**Zurückzulegen / owed YTD**) and compares it to what you've actually
  set aside (**Bereits zurückgelegt**). What's "set aside" is either the balance of a **designated
  reserve account** you pick (best practice — keep tax money in a separate Tagesgeld) or a
  manually-entered amount if you don't link one. You get a funded-% bar, your effective **reserve
  rate** (≈ % of freelance income), and a **recommended monthly set-aside** to be fully covered by
  December — which feeds the **Distribute leftover** card *off the top*. A linked account is
  **earmarked out of cash runway** so you don't count the Finanzamt's money as spendable. *Rough
  estimate — Soli, church tax and (for §19) VAT aren't included; not tax advice.*
- **Debts / "to pay off"** — one-off obligations; overdue ones surface in Alerts.
- **Budgets** — per-category monthly limits with spend-vs-limit progress bars.
- **Alerts** — over-budget categories, bills due soon, debts due, and **upcoming tax deadlines**
  (the next Einkommensteuer-Vorauszahlung / USt-Voranmeldung — see *Taxes → Steuertermine*).

### 📈 Analytics (sub-tab)

Charts and breakdowns — read-only, for spotting trends. Its own drag-to-reorder masonry grid.

- **Net-worth forecast** — net worth projected from your average monthly net + account returns.
- **Cashflow calendar** — a **day-by-day liquidity timeline** for the next 60–90 days, built only
  from *dated* events: recurring items + cashflow items, expected invoice payments (by due date),
  planned-purchase saves, debts, and tax-payment dates. It runs your liquid balance forward and
  **flags the tightest day** (and any day it would go negative). The dated counterpart to the
  smooth net-worth forecast.
- **Income & expense** — actual monthly in/out over a date range you pick.
- **Cashflow — last 12 months** — a per-month inflow/outflow bar chart from real transactions.
- **Spending by category** — a donut of where the money went, with a **CSV export** for your tax
  advisor.
- **Detected subscriptions** — recurring charges spotted in your transactions you can review/import.
- **💸 Money Wrapped** — a Spotify-Wrapped-style **year-in-review**: total earned / spent / net, hours
  worked, invoices sent, net-worth change, your **best client** by €/h, **priciest month**, **biggest
  single expense**, and **top spending categories**. Pick the year from the card. All derived from the
  transactions, time and invoices you already track.

> Tip: **Monthly cashflow** (planned recurring inflows/outflows that can be *materialized* into real
> dated transactions) is edited from the leftover/forecast flow; the 12-month chart here shows the
> *actuals* that result.

### ⚙️ Settings (sub-tab)

App-level configuration: manage your **transaction categories** (the taxonomy the rules engine and
budgets use). Your **business profile** (sender details, IBAN, §19 note, invoice
numbering) lives separately under **Business → Settings**.

It also holds the **🧭 money playbook**: the order to put euros to work (starter buffer → free
money → kill high-interest debt → full emergency fund → invest), and the principle behind it
("money flows to the highest guaranteed return"). Reference reading — not licensed financial advice.

---

## 🧑‍💻 Business

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
- **Group lines** (optional, no AI): instead of one line per entry, bundle them **by project,
  week, or month** into a single combined line each — a heading (project name / "KW 23 (…)" /
  "Juni 2026") plus the distinct tasks as bullets, with hours summed. Entries at different rates
  stay on separate lines. Turns ~25 raw entries into a handful of tidy lines you can still edit.
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
- **Rate advisor & what-if** — *what should I charge?* Enter a desired monthly take-home (defaults
  to your Sustainable Pay), billable hours/week and weeks/year, and it suggests the **hourly rate**
  that nets that after fixed costs and tax, vs. your current rate. Below it, **what-if sliders** —
  raise rates ±%, lose a client, or add a one-off purchase — show the live impact on your **monthly
  net, cash runway, annual profit and estimated tax** (a rough flat-marginal-rate planning aid, not
  tax advice).
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

---

## 🧾 Taxes

Everything you need to prepare your German freelance taxes (Einnahmenüberschussrechnung → ELSTER)
for one tax year, built from the transactions you already track. Pick the **tax year** at the top
of the Overview (defaults to the last completed year — the one you file).

### Overview (the EÜR)
- **Betriebseinnahmen − Betriebsausgaben = Gewinn.** Income is every transaction marked **Business**
  (the Business/Private toggle when you add or edit a transaction) with a positive amount; expenses
  come from three buckets:
  - **Direct (100%)** — business-flagged costs, grouped by category. Off-balance bookkeeping rows
    (the `excluded` flag) are **included** here — they still count for taxes.
  - **Mixed-use (%)** — categories you marked as partly business in Settings (e.g. Internet 50%),
    applied to that category's transactions that are *not* marked business (so nothing is counted
    twice). You can also set a **business deductible %** on a *single* transaction (edit it, or the
    "details" section when adding) — that per-transaction share overrides the category rate (and the
    business flag's 100%) for just that expense, and works even in categories without a mixed rate.
    Blank = fall back to the business flag / category rate.
  - **Allowances** — the **Homeoffice-Pauschale** (6 €/day, max 1.260 €) or a **häusliches
    Arbeitszimmer** (the 1.260 € Jahrespauschale or actual area-based cost), and business **travel**
    (km × your rate, default 0,30 €/km).
- **Income-tax estimate.** A rough §32a estimate of the extra income tax your freelance profit adds,
  stacked on top of the *übrige Einkünfte* (e.g. salary) you enter. **It's an estimate, not tax
  advice** — Soli and church tax are not included.
- **Erstattung / Nachzahlung (the full personal picture).** A separate card estimates what you'll
  still settle with the Finanzamt. Your **einbehaltene Lohnsteuer** is treated as having already
  covered the income tax on your **salary** (that's what payroll withholding does), so the balance
  is just the **marginal §32a tax your freelance profit adds**, minus any **Einkommensteuer-
  Vorauszahlungen** — giving your likely **refund (Erstattung)** or **amount owed (Nachzahlung)**.
  Enter the **einbehaltene Lohnsteuer** (line 4 of your *Lohnsteuerbescheinigung* — not Soli or
  church tax) and any prepayments under *Angaben*. A rough estimate only: it uses the single
  Grundtarif (no Ehegatten-Splitting) and excludes Soli/church tax.
- **Steuertermine <year>.** The year's deadlines: the four **Einkommensteuer-Vorauszahlung** dates
  (10 Mar/Jun/Sep/Dec, each with an estimated quarter amount from your prepayment or the §32a
  projection), the quarterly **Umsatzsteuer-Voranmeldung** (only shown when you're *not*
  Kleinunternehmer), and the **EÜR/Steuererklärung filing date**. The next ones also pop up in the
  **Alerts** card and on the **Cashflow calendar**. Statutory dates (no weekend/holiday shift);
  estimate only, not tax advice.
- **Angaben für <year>.** Edit the year-specific numbers here — gross salary / other income,
  einbehaltene Lohnsteuer, Einkommensteuer-Vorauszahlungen, Homeoffice days, business km — and the
  figures recompute.
- **🚗 Fahrtenbuch.** A proper **per-trip mileage log** (date · route · km · purpose · optional
  client) for the year. The summed kilometres **flow into the EÜR's Reisekosten** (km × your rate),
  *overriding* the single manual "business km" figure whenever any trips are logged — so adding a
  trip updates the EÜR above. Tag a client to keep travel attributable.
- **Erfasste Buchungen.** The underlying transactions (income / direct / mixed) with the amount
  counted toward the EÜR — mixed rows also show the **business %** applied — so you can check every
  euro. Export them as **CSV** (now including a `percent` column).

### ELSTER helper
Click **Generate ELSTER prompt** to produce a ready-to-paste text: all your EÜR figures grouped by
the Anlage EÜR's sections (Betriebseinnahmen, Arbeitsmittel, Arbeitszimmer/Homeoffice, Reisekosten,
gemischte Kosten …), your Freiberufler/Gewerbe + §19 status, and the profit. Paste it into the
**Claude browser extension** (or any AI) to be guided through filling the Anlage EÜR in **Mein
ELSTER**. It deliberately doesn't hard-code Zeilen numbers (they change each year) — it tells the
assistant to match each value to the current form.

### Settings (how your taxes work)
The stable setup, separate from the per-year numbers: **Freiberufler
(Anlage S) / Gewerbe (Anlage G)**, the **Arbeitszimmer/Homeoffice** mode (none / Pauschale / room),
the **km rate**, and a **mixed-use %** per expense category (Internet, Mobile, Kfz …).

## Cross-app niceties
- **⌘K command palette** — press ⌘K (Ctrl+K) anywhere to jump to any section or toggle the theme.
- **Idle detection** — if the timer runs 15 min without activity, it asks whether you're still working.
- **Mobile-optimised** — on phones (≤ 760px) the desktop sidebar is replaced by a fixed **bottom
  tab bar** (💰 Finances · 🧑‍💻 Business · 🧾 Taxes · ☰ More), with theme/account/logout in the
  "More" sheet. Section sub-tabs become a horizontally scrollable strip, paired form fields stack,
  wide tables scroll sideways inside their card, inputs use 16px text (no iOS zoom-on-focus), and
  modals dock as full-width bottom sheets. iPhone safe-area insets are respected.
- **Installable (PWA)** — "Add to Home Screen" on mobile/desktop for an app-like, fullscreen launch;
  the shell works offline after first load.

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
