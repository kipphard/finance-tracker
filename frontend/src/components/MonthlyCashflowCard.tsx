import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useApi } from "../hooks/useApi";
import { useTheme } from "../theme";
import type { MonthlyCashflowPoint } from "../api/types";
import { money, num } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

export function MonthlyCashflowCard({ className }: { className?: string }) {
  const state = useApi<MonthlyCashflowPoint[]>("/reports/monthly-cashflow?months=12");
  const { grid, axis } = useTheme();

  return (
    <Card title="Cashflow — last 12 months (actual)" className={className}>
      <Async state={state}>
        {(points) => {
          const data = points.map((p) => ({
            month: p.month.slice(2), // YY-MM
            Inflow: num(p.inflow),
            Outflow: num(p.outflow),
          }));
          const any = data.some((d) => d.Inflow !== 0 || d.Outflow !== 0);
          if (!any)
            return (
              <div className="empty">
                No transactions yet — add income/expenses and this fills in month by month.
              </div>
            );
          return (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data} barGap={3} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
                <XAxis dataKey="month" tick={{ fill: axis, fontSize: 11 }} stroke={grid} />
                <YAxis tick={{ fill: axis, fontSize: 11 }} stroke={grid} width={70}
                  tickFormatter={(v) => money(v)} />
                <Tooltip formatter={(v: number) => money(v)} cursor={{ fill: "transparent" }}
                  contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, color: "var(--text)" }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="Inflow" fill="var(--positive)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Outflow" fill="var(--negative)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          );
        }}
      </Async>
    </Card>
  );
}
