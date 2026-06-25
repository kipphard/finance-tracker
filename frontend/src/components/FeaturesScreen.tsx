import { Link } from "react-router-dom";
import { Card } from "./Card";

// A living, data-driven catalogue of everything the app does. Adding a future feature later is a
// single entry below — never a rewrite. (This app isn't i18n'd, so strings are inline; keep this
// page in sync whenever a feature ships — see the "definition of done" note in the README.)
interface Feat {
  id: string;
  icon: string;
  name: string;
  desc: string; // one line: what it is
  how: string; // one line: how to use it
  to?: string; // deep-link to the screen; omit for info-only items
}
interface Group {
  id: string;
  label: string;
  items: Feat[];
}

const GROUPS: Group[] = [
  {
    id: "accounts",
    label: "Accounts & net worth",
    items: [
      { id: "accounts", icon: "💳", name: "Accounts", to: "/",
        desc: "Track checking, savings, cash and brokerage accounts in one place.",
        how: "Overview → Accounts → + Account. Net worth is the sum of each account's transactions." },
      { id: "networth", icon: "📈", name: "Net worth & trend", to: "/",
        desc: "Headline net worth with a daily-snapshot trend chart.",
        how: "Shown at the top of Overview; snapshots run nightly or via “Take snapshot”." },
      { id: "reconcile", icon: "⚖️", name: "Reconcile balance", to: "/",
        desc: "Assert an account's real balance on a date and book one adjusting entry to fix drift.",
        how: "Overview → Accounts → ⚖ on a row → enter the real balance." },
      { id: "transfers", icon: "⇄", name: "Transfers", to: "/",
        desc: "Move money between two accounts without touching income/expense.",
        how: "Overview → Accounts → ⇄ Transfer." },
    ],
  },
  {
    id: "transactions",
    label: "Transactions",
    items: [
      { id: "txns", icon: "🧾", name: "Transactions", to: "/",
        desc: "Add income and expenses by hand, then edit or categorise them.",
        how: "Overview → Transactions → + Transaction." },
      { id: "import", icon: "⬆️", name: "CSV import", to: "/",
        desc: "Bulk-import a bank statement; German number/date formats and duplicates handled.",
        how: "Overview → Transactions → import a CSV (;-delimited, DD.MM.YYYY, 1.234,56)." },
      { id: "categories", icon: "🏷️", name: "Categories & rules", to: "/settings",
        desc: "Organise spending with a category taxonomy and payee → category rules.",
        how: "Finances → Settings → Categories; reclassifying a transaction can save a rule." },
      { id: "receipts", icon: "🔖", name: "Tags & receipts", to: "/",
        desc: "Add free-text tags and attach PDF/image receipts to a transaction.",
        how: "Edit a transaction to add tags or upload a receipt." },
      { id: "recurring", icon: "🔁", name: "Recurring transactions", to: "/",
        desc: "Templates auto-post on a schedule with catch-up and de-duplication.",
        how: "Mark a transaction recurring; due ones post automatically (see the Scheduled card)." },
      { id: "offbalance", icon: "👻", name: "Off-balance entries", to: "/",
        desc: "Record-only rows kept for reports and tax but excluded from balances.",
        how: "Tick “off-balance” when adding a transaction." },
    ],
  },
  {
    id: "planning",
    label: "Planning & saving",
    items: [
      { id: "runway", icon: "🛟", name: "Cash runway", to: "/",
        desc: "How many months your liquid balance lasts at the current monthly net.",
        how: "Shown on Overview; earmarked goal money is excluded." },
      { id: "paycheck", icon: "💸", name: "Sustainable monthly pay", to: "/",
        desc: "A safe “pay yourself” figure: trailing net minus tax reserve and planned savings, capped by liquid.",
        how: "Overview → Sustainable monthly pay card." },
      { id: "allocation", icon: "🪣", name: "Distribute leftover", to: "/",
        desc: "Split each month's leftover into buckets and book the moves in one click.",
        how: "Overview → Distribute leftover → Apply this month." },
      { id: "emergency", icon: "🚑", name: "Emergency fund", to: "/",
        desc: "Track a target of N× monthly costs and how funded you are.",
        how: "Overview → Emergency fund; link an account to track it live." },
      { id: "taxreserve", icon: "🏛️", name: "Steuerrücklage (tax reserve)", to: "/",
        desc: "Estimates the income tax owed on freelance profit YTD vs. what you've set aside.",
        how: "Overview → Steuerrücklage; link a dedicated reserve account." },
      { id: "planned", icon: "🎯", name: "Planned purchases", to: "/",
        desc: "A wishlist with a monthly save plan and a projected affordability date.",
        how: "Overview → Planned purchases → add an item and a monthly save." },
      { id: "debts", icon: "💳", name: "Debts to pay off", to: "/",
        desc: "One-off obligations with due dates; overdue ones surface in Alerts.",
        how: "Overview → Debts." },
      { id: "budgets", icon: "📊", name: "Budgets", to: "/",
        desc: "Per-category monthly spending limits with progress bars.",
        how: "Overview → Budgets." },
      { id: "alerts", icon: "🔔", name: "Alerts", to: "/",
        desc: "Over-budget categories, bills due, debts and upcoming tax deadlines.",
        how: "Overview → Alerts card." },
    ],
  },
  {
    id: "analytics",
    label: "Analytics & forecasts",
    items: [
      { id: "forecast", icon: "🔮", name: "Net-worth forecast", to: "/analytics",
        desc: "Projects net worth from your average monthly net and account returns.",
        how: "Analytics → Net worth forecast." },
      { id: "calendar", icon: "📅", name: "Cashflow calendar", to: "/analytics",
        desc: "Day-by-day liquid balance for the next 60–90 days; flags the tightest day.",
        how: "Analytics → Cashflow calendar; toggle 60/90 days." },
      { id: "incomeexpense", icon: "⚖️", name: "Income & expense", to: "/analytics",
        desc: "Actual monthly in/out over a date range you pick.",
        how: "Analytics → Income & expense." },
      { id: "cashflow12", icon: "📊", name: "12-month cashflow", to: "/analytics",
        desc: "Per-month inflow/outflow bars from your real transactions.",
        how: "Analytics → Cashflow (last 12 months)." },
      { id: "categorybreakdown", icon: "🍩", name: "Spending by category", to: "/analytics",
        desc: "A donut of where the money went, with a CSV export.",
        how: "Analytics → Spending by category." },
      { id: "subscriptions", icon: "🔁", name: "Detected subscriptions", to: "/analytics",
        desc: "Recurring charges spotted in your transactions, to review or import.",
        how: "Analytics → Detected subscriptions." },
      { id: "wrapped", icon: "💸", name: "Money Wrapped", to: "/analytics",
        desc: "A year-in-review recap: earned/spent/net, hours, best client, priciest month, top categories.",
        how: "Analytics → Money Wrapped; pick a year." },
    ],
  },
  {
    id: "time",
    label: "Time & clients (Business)",
    items: [
      { id: "timer", icon: "⏱️", name: "Time tracking", to: "/business",
        desc: "Start/stop a timer per client (it survives reloads) or log entries by hand.",
        how: "Business → Time → start the timer or + Manual entry." },
      { id: "clients", icon: "👥", name: "Clients", to: "/business/clients",
        desc: "Per-client rate, hour budget, contact details and tracked/unbilled totals.",
        how: "Business → Clients → add a client." },
      { id: "projects", icon: "📁", name: "Projects", to: "/business/clients",
        desc: "Projects under a client with optional rate/budget overrides.",
        how: "Business → Clients → add a project to a client." },
    ],
  },
  {
    id: "invoices",
    label: "Invoices (Business)",
    items: [
      { id: "invoices", icon: "📄", name: "Invoices", to: "/business/invoices",
        desc: "Build invoices from tracked time or as a flat fee; DE/EN, §19 or 19% VAT.",
        how: "Business → Invoices → New invoice." },
      { id: "recurringinv", icon: "🔁", name: "Recurring invoices", to: "/business/invoices",
        desc: "Retainer templates that auto-draft an invoice each period.",
        how: "Business → Invoices → set up a recurring invoice." },
      { id: "invoicepdf", icon: "🧾", name: "PDF & GiroCode", to: "/business/invoices",
        desc: "Download a PDF invoice with a scan-to-pay GiroCode (EPC-QR).",
        how: "Open an invoice → Download PDF." },
      { id: "invoiceemail", icon: "✉️", name: "Email & reminders", to: "/business/invoices",
        desc: "Send invoices by email and escalate overdue ones (Mahnwesen).",
        how: "Open an invoice → Email, or send a payment reminder." },
      { id: "payments", icon: "✅", name: "Payment matching", to: "/business/invoices",
        desc: "Auto-marks an invoice paid from the matching bank transaction.",
        how: "Tag a transaction with the invoice number; the status flips to paid." },
      { id: "bizinsights", icon: "📈", name: "Business insights", to: "/business/insights",
        desc: "Client profitability (effective €/h) and project budget burn-down.",
        how: "Business → Insights." },
      { id: "rateadvisor", icon: "🧮", name: "Rate advisor & what-if", to: "/business/insights",
        desc: "Suggests an hourly rate to hit a take-home target, plus what-if sliders for rate, clients and purchases.",
        how: "Business → Insights → Rate advisor & what-if." },
    ],
  },
  {
    id: "taxes",
    label: "Taxes (German EÜR)",
    items: [
      { id: "eur", icon: "🧾", name: "EÜR", to: "/taxes",
        desc: "Einnahmenüberschussrechnung: income − expenses = profit for a tax year.",
        how: "Taxes → pick a year; income comes from Business-flagged transactions." },
      { id: "incometax", icon: "💶", name: "Income-tax estimate", to: "/taxes",
        desc: "A rough §32a estimate of the income tax your freelance profit adds.",
        how: "Taxes → Overview (Einkommensteuer-Schätzung)." },
      { id: "refund", icon: "💱", name: "Erstattung / Nachzahlung", to: "/taxes",
        desc: "Your likely refund or amount owed after withheld tax and prepayments.",
        how: "Taxes → enter Lohnsteuer and Vorauszahlungen under Angaben." },
      { id: "deadlines", icon: "📅", name: "Steuertermine", to: "/taxes",
        desc: "Quarterly Vorauszahlung, USt-Voranmeldung and the EÜR filing date.",
        how: "Taxes → Steuertermine; the next ones also show up in Alerts." },
      { id: "fahrtenbuch", icon: "🚗", name: "Fahrtenbuch", to: "/taxes",
        desc: "A per-trip mileage log (date, route, km, purpose, client) whose km feed the EÜR Reisekosten.",
        how: "Taxes → Overview → Fahrtenbuch; add trips for the year." },
      { id: "elster", icon: "📋", name: "ELSTER prompt", to: "/taxes",
        desc: "Generates a copy-paste prompt to help fill the Anlage EÜR in Mein ELSTER.",
        how: "Taxes → ELSTER prompt → copy it into your assistant of choice." },
      { id: "taxexport", icon: "⬇️", name: "Tax CSV export", to: "/taxes",
        desc: "Export every counted booking with its deductible amount for your advisor.",
        how: "Taxes → ⬇ CSV." },
      { id: "taxsettings", icon: "⚙️", name: "Tax settings", to: "/taxes/settings",
        desc: "Business type, mixed-use %, home-office mode and km rate.",
        how: "Taxes → Settings." },
    ],
  },
  {
    id: "app",
    label: "App & your data",
    items: [
      { id: "palette", icon: "⌨️", name: "Command palette",
        desc: "Jump to any section or toggle the theme from the keyboard.",
        how: "Press ⌘K (Ctrl+K) anywhere." },
      { id: "theme", icon: "🌙", name: "Dark mode",
        desc: "Light/dark theme, remembered per device.",
        how: "Toggle from the sidebar or the “More” menu." },
      { id: "playbook", icon: "🧭", name: "Money playbook", to: "/settings",
        desc: "A reference order for putting your euros to work.",
        how: "Finances → Settings → money playbook." },
      { id: "settings", icon: "⚙️", name: "Settings & categories", to: "/settings",
        desc: "Manage your category taxonomy and app preferences.",
        how: "Finances → Settings." },
      { id: "pwa", icon: "📱", name: "Install as an app (PWA)",
        desc: "Install to your home screen; on phones the layout uses a bottom nav.",
        how: "Use your browser's “Add to Home Screen”." },
      { id: "data", icon: "📦", name: "Export or delete your data",
        desc: "Full GDPR data export and account deletion.",
        how: "Via the account API (GET /api/me/export, DELETE /api/me)." },
    ],
  },
];

export function FeaturesScreen() {
  // scrollIntoView via buttons (not <a href="#…">) — router-safe under HashRouter.
  const jumpTo = (id: string) =>
    document.getElementById(`feat-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <div className="container">
      <div className="page-head">
        <h1>⭐ Features</h1>
        <p className="muted">Everything this app can do — with a one-line how-to for each.</p>
      </div>

      <nav className="feature-nav" aria-label="Feature categories">
        {GROUPS.map((g) => (
          <button key={g.id} type="button" className="feature-nav__chip" onClick={() => jumpTo(g.id)}>
            {g.label}
          </button>
        ))}
      </nav>

      <div className="card-stack">
        {GROUPS.map((g) => (
          <section key={g.id} id={`feat-${g.id}`} className="feature-group">
            <Card title={g.label}>
              <ul className="feature-list">
                {g.items.map((f) => (
                  <li key={f.id} className="feature-list__item">
                    <div className="feature-list__head">
                      <strong>
                        <span aria-hidden>{f.icon}</span> {f.name}
                      </strong>
                      {f.to && (
                        <Link className="btn btn--ghost btn--sm" to={f.to}>
                          Open
                        </Link>
                      )}
                    </div>
                    <p>{f.desc}</p>
                    <p className="muted">→ {f.how}</p>
                  </li>
                ))}
              </ul>
            </Card>
          </section>
        ))}
      </div>
    </div>
  );
}
