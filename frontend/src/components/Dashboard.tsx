import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { apiPost } from "../api/client";
import { useCardOrder } from "../hooks/useCardOrder";
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
import { EmergencyFundCard } from "./EmergencyFundCard";
import { AllocationCard } from "./AllocationCard";
import { TransactionsTable } from "./TransactionsTable";
import { PlaybookCard } from "./PlaybookCard";

// Cards that span the full width of the dashboard grid.
const WIDE = new Set(["playbook", "networth", "cashflow", "transactions"]);

// Default top-to-bottom priority. Forecast sits high (above spending-by-category
// and detected subscriptions); categories at the very bottom. Users can drag to reorder.
const DEFAULT_ORDER = [
  "playbook",
  "networth",
  "income",
  "forecast",
  "cashflow",
  "transactions",
  "allocation",
  "alerts",
  "accounts",
  "scheduled",
  "debts",
  "emergency",
  "budgets",
  "category",
  "detected",
  "categories",
];

export function Dashboard() {
  const [ready, setReady] = useState(false);
  const [order, setOrder] = useCardOrder(DEFAULT_ORDER);
  const dragId = useRef<string | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);

  // Post any due recurring transactions before the cards fetch, so they show up.
  useEffect(() => {
    apiPost("/cashflow/run")
      .catch(() => {})
      .finally(() => setReady(true));
  }, []);

  const cards: Record<string, ReactNode> = {
    playbook: <PlaybookCard />,
    networth: <NetWorthHero />,
    income: <IncomeExpenseCard />,
    forecast: <ForecastCard />,
    cashflow: <MonthlyCashflowCard />,
    transactions: <TransactionsTable />,
    alerts: <AlertsCard />,
    accounts: <AccountsCard />,
    scheduled: <ScheduledCard />,
    debts: <DebtsCard />,
    emergency: <EmergencyFundCard />,
    allocation: <AllocationCard />,
    budgets: <BudgetsCard />,
    category: <CategoryBreakdownCard />,
    detected: <RecurringCard />,
    categories: <CategoriesCard />,
  };

  const onDragEnter = (overId: string) => {
    const from = dragId.current;
    if (!from || from === overId) return;
    const next = order.filter((k) => k !== from);
    next.splice(next.indexOf(overId), 0, from);
    setOrder(next);
  };
  const endDrag = () => {
    dragId.current = null;
    setDragging(null);
  };

  return (
      <div className="container">
        {!ready ? (
          <div className="muted">Loading…</div>
        ) : (
          <div className="dash">
            {order
              .filter((id) => cards[id])
              .map((id) => (
                <div
                  key={id}
                  className={
                    "dash__cell" +
                    (WIDE.has(id) ? " dash__cell--wide" : "") +
                    (dragging === id ? " is-dragging" : "")
                  }
                  onDragEnter={() => onDragEnter(id)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    endDrag();
                  }}
                >
                  <span
                    className="dash__grip"
                    draggable
                    title="Drag to reorder"
                    onDragStart={(e) => {
                      dragId.current = id;
                      setDragging(id);
                      const cell = (e.currentTarget as HTMLElement).closest(".dash__cell") as HTMLElement | null;
                      if (cell) e.dataTransfer.setDragImage(cell, 24, 24);
                      e.dataTransfer.effectAllowed = "move";
                    }}
                    onDragEnd={endDrag}
                  >
                    ⠿
                  </span>
                  {cards[id]}
                </div>
              ))}
          </div>
        )}
      </div>
  );
}
