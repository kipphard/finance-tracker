import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { useApi } from "../hooks/useApi";
import type { CategoryBreakdownItem } from "../api/types";
import { money, num } from "../lib/format";
import { CHART_COLORS } from "../lib/colors";
import { Card } from "./Card";
import { Async } from "./Async";

export function CategoryBreakdownCard({ className }: { className?: string }) {
  const state = useApi<CategoryBreakdownItem[]>("/reports/category-breakdown");
  return (
    <Card title="Spending by category" className={className}>
      <Async state={state}>
        {(items) => {
          const expenses = items
            .filter((i) => num(i.total) < 0)
            .map((i) => ({ name: i.name, value: Math.abs(num(i.total)), is_fixed: i.is_fixed }));
          if (expenses.length === 0)
            return <div className="empty">No categorized spending yet.</div>;

          const fixed = expenses.filter((e) => e.is_fixed).reduce((a, b) => a + b.value, 0);
          const variable = expenses.filter((e) => !e.is_fixed).reduce((a, b) => a + b.value, 0);

          return (
            <>
              <ResponsiveContainer width="100%" height={290}>
                <PieChart>
                  <Pie data={expenses} dataKey="value" nameKey="name" cx="50%" cy="50%"
                    innerRadius={70} outerRadius={112} paddingAngle={2} stroke="none">
                    {expenses.map((_, idx) => (
                      <Cell key={idx} fill={CHART_COLORS[idx % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => money(v)}
                    contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, color: "var(--text)" }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
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
