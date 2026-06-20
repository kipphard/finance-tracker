import { useEffect, useState } from "react";
import { useAuth } from "../auth";
import { useTheme } from "../theme";
import { apiPost } from "../api/client";
import { NetWorthHero } from "./NetWorthHero";
import { AlertsCard } from "./AlertsCard";
import { MonthlyCashflowCard } from "./MonthlyCashflowCard";
import { IncomeExpenseCard } from "./IncomeExpenseCard";
import { ForecastCard } from "./ForecastCard";
import { CategoryBreakdownCard } from "./CategoryBreakdownCard";
import { AccountsCard } from "./AccountsCard";
import { BudgetsCard } from "./BudgetsCard";
import { RecurringCard } from "./RecurringCard";
import { ScheduledCard } from "./ScheduledCard";
import { CategoriesCard } from "./CategoriesCard";
import { DebtsCard } from "./DebtsCard";
import { TransactionsTable } from "./TransactionsTable";

export function Dashboard() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const [ready, setReady] = useState(false);

  // Post any due recurring transactions before the cards fetch, so they show up.
  useEffect(() => {
    apiPost("/cashflow/run")
      .catch(() => {})
      .finally(() => setReady(true));
  }, []);

  return (
    <>
      <header className="topbar">
        <div className="topbar__title">
          <span>💰</span> Finance Tracker
        </div>
        <div className="topbar__right">
          <button className="icon-btn" onClick={toggle} aria-label="Toggle theme" title="Toggle light / dark">
            {theme === "light" ? "🌙" : "☀️"}
          </button>
          <div className="topbar__user">
            <span className="muted">{user?.email}</span>
            <button className="btn btn--ghost btn--sm" onClick={logout}>Log out</button>
          </div>
        </div>
      </header>

      <div className="container">
        {!ready ? (
          <div className="muted">Loading…</div>
        ) : (
          <div className="stack">
            {/* Most important, full width */}
            <div className="row-2">
              <NetWorthHero />
              <IncomeExpenseCard />
            </div>
            <MonthlyCashflowCard />
            <TransactionsTable />

            {/* Secondary cards, tightly packed */}
            <div className="masonry">
              <AlertsCard />
              <AccountsCard />
              <ScheduledCard />
              <DebtsCard />
              <BudgetsCard />
              <ForecastCard />
              <CategoryBreakdownCard />
              <RecurringCard />
              <CategoriesCard />
            </div>
          </div>
        )}
      </div>
    </>
  );
}
