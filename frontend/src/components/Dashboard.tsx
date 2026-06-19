import { useAuth } from "../auth";
import { useTheme } from "../theme";
import { NetWorthHero } from "./NetWorthHero";
import { AlertsCard } from "./AlertsCard";
import { CashflowCard } from "./CashflowCard";
import { ForecastCard } from "./ForecastCard";
import { CategoryBreakdownCard } from "./CategoryBreakdownCard";
import { AccountsCard } from "./AccountsCard";
import { BudgetsCard } from "./BudgetsCard";
import { RecurringCard } from "./RecurringCard";
import { CategoriesCard } from "./CategoriesCard";
import { TransactionsTable } from "./TransactionsTable";

export function Dashboard() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();

  return (
    <>
      <header className="topbar">
        <div className="topbar__title">
          <span>💰</span> Finance Tracker
        </div>
        <div className="topbar__right">
          <button
            className="icon-btn"
            onClick={toggle}
            aria-label="Toggle theme"
            title="Toggle light / dark"
          >
            {theme === "light" ? "🌙" : "☀️"}
          </button>
          <div className="topbar__user">
            <span className="muted">{user?.email}</span>
            <button className="btn btn--ghost btn--sm" onClick={logout}>
              Log out
            </button>
          </div>
        </div>
      </header>

      <div className="container">
        <div className="grid">
          <NetWorthHero className="col-8" />
          <AlertsCard className="col-4" />

          <CashflowCard className="col-4" />
          <ForecastCard className="col-4" />
          <CategoryBreakdownCard className="col-4" />

          <AccountsCard className="col-4" />
          <BudgetsCard className="col-4" />
          <RecurringCard className="col-4" />

          <CategoriesCard className="col-4" />
          <TransactionsTable className="col-8" />
        </div>
      </div>
    </>
  );
}
