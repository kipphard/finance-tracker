import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { apiPost } from "../api/client";
import { CardGrid } from "./CardGrid";
import { NetWorthHero } from "./NetWorthHero";
import { AccountsCard } from "./AccountsCard";
import { RunwayCard } from "./RunwayCard";
import { AllocationCard } from "./AllocationCard";
import { PlannedPurchasesCard } from "./PlannedPurchasesCard";
import { EmergencyFundCard } from "./EmergencyFundCard";
import { TaxReserveCard } from "./TaxReserveCard";
import { DebtsCard } from "./DebtsCard";
import { BudgetsCard } from "./BudgetsCard";
import { AlertsCard } from "./AlertsCard";
import { ScheduledCard } from "./ScheduledCard";
import { TransactionsTable } from "./TransactionsTable";

// "Finances" = the money cockpit: things you act on. Charts/trends live under Analytics.
const WIDE = new Set(["networth", "transactions"]);
const DEFAULT_ORDER = [
  "networth",
  "accounts",
  "runway",
  "allocation",
  "planned",
  "emergency",
  "taxreserve",
  "debts",
  "budgets",
  "alerts",
  "scheduled",
  "transactions",
];

export function Dashboard() {
  const [ready, setReady] = useState(false);

  // Post any due recurring transactions before the cards fetch, so they show up.
  useEffect(() => {
    apiPost("/cashflow/run")
      .catch(() => {})
      .finally(() => setReady(true));
  }, []);

  const cards: Record<string, ReactNode> = {
    networth: <NetWorthHero />,
    accounts: <AccountsCard />,
    runway: <RunwayCard />,
    allocation: <AllocationCard />,
    planned: <PlannedPurchasesCard />,
    emergency: <EmergencyFundCard />,
    taxreserve: <TaxReserveCard />,
    debts: <DebtsCard />,
    budgets: <BudgetsCard />,
    alerts: <AlertsCard />,
    scheduled: <ScheduledCard />,
    transactions: <TransactionsTable />,
  };

  if (!ready) return <div className="muted">Loading…</div>;
  return (
    <CardGrid storageKey="ft_card_order_finances" defaultOrder={DEFAULT_ORDER} wide={WIDE} cards={cards} />
  );
}
