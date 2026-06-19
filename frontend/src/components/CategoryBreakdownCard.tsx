import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { useApi } from "../hooks/useApi";
import type { CategoryBreakdownItem } from "../api/types";
import { money, num } from "../lib/format";
import { CHART_COLORS } from "../lib/colors";
import { Card } from "./Card";
import { Async } from "./Async";

export function CategoryBreakdownCard() {
  const state = useApi<CategoryBreakdownItem[]>("/reports/category-breakdown");
  return (
    <Card title="Spending by category">
      <Async state={state}>
        {(items) => {
          // Spending = negative totals; show as positive magnitudes.
          const expenses = items
            .filter((i) => num(i.total) < 0)
            .map((i) => ({
              name: i.name,
              value: Math.abs(num(i.total)),
              is_fixed: i.is_fixed,
            }));
          if (expenses.length === 0)
            return <div className="empty">No categorized spending yet.</div>;

          const fixed = expenses
            .filter((e) => e.is_fixed)
            .reduce((a, b) => a + b.value, 0);
          const variable = expenses
            .filter((e) => !e.is_fixed)
            .reduce((a, b) => a + b.value, 0);

          return (
            <>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={expenses}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={82}
                    label={(e: { name?: string }) => e.name ?? ""}
                  >
                    {expenses.map((_, idx) => (
                      <Cell key={idx} fill={CHART_COLORS[idx % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => money(v)} />
                </PieChart>
              </ResponsiveContainer>
              <div className="metric-row" style={{ marginTop: 8 }}>
                <div className="metric-block">
                  <div className="label">Fixed</div>
                  <div className="value">{money(fixed)}</div>
                </div>
                <div className="metric-block">
                  <div className="label">Variable</div>
                  <div className="value">{money(variable)}</div>
                </div>
              </div>
            </>
          );
        }}
      </Async>
    </Card>
  );
}
