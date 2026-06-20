import { useState } from "react";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { useApi } from "../hooks/useApi";
import type { CategoryOut, TransactionOut } from "../api/types";
import { money, num } from "../lib/format";
import { CHART_COLORS } from "../lib/colors";
import { Card } from "./Card";
import { Async } from "./Async";

export function CategoryBreakdownCard({ className }: { className?: string }) {
  const txns = useApi<TransactionOut[]>("/transactions");
  const cats = useApi<CategoryOut[]>("/categories");
  const [tag, setTag] = useState("all");

  const allTags = [
    ...new Set((txns.data ?? []).filter((t) => !t.is_transfer).flatMap((t) => t.tags ?? [])),
  ].sort();
  const action =
    allTags.length > 0 ? (
      <select className="select" value={tag} onChange={(e) => setTag(e.target.value)} style={{ fontSize: 13 }}>
        <option value="all">All</option>
        {allTags.map((t) => (
          <option key={t} value={t}>#{t}</option>
        ))}
      </select>
    ) : undefined;

  return (
    <Card title="Spending by category" className={className} action={action}>
      <Async state={txns}>
        {(list) => {
          const catMap = new Map((cats.data ?? []).map((c) => [c.id, c]));
          const spendable = list.filter((t) => !t.is_transfer); // transfers aren't spending
          const filtered = tag === "all" ? spendable : spendable.filter((t) => (t.tags ?? []).includes(tag));

          // Sum each category's signed total, then keep the spending (negative) side.
          const byCat = new Map<string, number>();
          for (const t of filtered) {
            const key = t.category_id ?? "uncat";
            byCat.set(key, (byCat.get(key) ?? 0) + num(t.amount));
          }
          const expenses = [...byCat.entries()]
            .map(([key, total]) => {
              const c = key === "uncat" ? undefined : catMap.get(key);
              return { name: c?.name ?? "Uncategorized", value: total, is_fixed: c?.is_fixed ?? false };
            })
            .filter((e) => e.value < 0)
            .map((e) => ({ ...e, value: Math.abs(e.value) }))
            .sort((a, b) => b.value - a.value);

          if (expenses.length === 0)
            return (
              <div className="empty">
                No categorized spending{tag !== "all" ? ` tagged #${tag}` : ""} yet.
              </div>
            );

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
