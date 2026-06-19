import { useApi } from "../hooks/useApi";
import type { NetWorthOut } from "../api/types";
import { money } from "../lib/format";
import { NetWorthCard } from "./NetWorthCard";
import { NetWorthTrend } from "./NetWorthTrend";
import { CashflowCard } from "./CashflowCard";
import { CategoryBreakdownCard } from "./CategoryBreakdownCard";
import { AccountsCard } from "./AccountsCard";
import { RecurringCard } from "./RecurringCard";
import { TransactionsTable } from "./TransactionsTable";
import { AlertsCard } from "./AlertsCard";
import { BudgetsCard } from "./BudgetsCard";
import { ForecastCard } from "./ForecastCard";

export function Dashboard() {
  const nw = useApi<NetWorthOut>("/networth");

  return (
    <>
      <header className="topbar">
        <div className="topbar__title">💰 Finance Tracker</div>
        <div className="topbar__total">
          <div className="label">Net worth</div>
          <div className="value">
            {nw.data ? money(nw.data.total, nw.data.base_currency) : "…"}
          </div>
        </div>
      </header>

      <div className="container">
        <div className="grid">
          <AlertsCard />
          <NetWorthCard />
          <NetWorthTrend />
          <ForecastCard />
          <CashflowCard />
          <CategoryBreakdownCard />
          <BudgetsCard />
          <AccountsCard />
          <RecurringCard />
          <TransactionsTable />
        </div>
      </div>
    </>
  );
}
