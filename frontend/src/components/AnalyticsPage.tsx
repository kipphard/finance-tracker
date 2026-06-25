import type { ReactNode } from "react";
import { CardGrid } from "./CardGrid";
import { IncomeExpenseCard } from "./IncomeExpenseCard";
import { ForecastCard } from "./ForecastCard";
import { CashflowCalendarCard } from "./CashflowCalendarCard";
import { MoneyWrappedCard } from "./MoneyWrappedCard";
import { MonthlyCashflowCard } from "./MonthlyCashflowCard";
import { CategoryBreakdownCard } from "./CategoryBreakdownCard";
import { RecurringCard } from "./RecurringCard";

// "Analytics" = read-only charts & breakdowns you look at to understand trends.
const WIDE = new Set(["cashflow", "calendar", "wrapped"]);
const DEFAULT_ORDER = ["forecast", "calendar", "wrapped", "income", "cashflow", "category", "detected"];

export function AnalyticsPage() {
  const cards: Record<string, ReactNode> = {
    forecast: <ForecastCard />,
    calendar: <CashflowCalendarCard />,
    wrapped: <MoneyWrappedCard />,
    income: <IncomeExpenseCard />,
    cashflow: <MonthlyCashflowCard />,
    category: <CategoryBreakdownCard />,
    detected: <RecurringCard />,
  };

  return (
    <CardGrid storageKey="ft_card_order_analytics" defaultOrder={DEFAULT_ORDER} wide={WIDE} cards={cards} />
  );
}
