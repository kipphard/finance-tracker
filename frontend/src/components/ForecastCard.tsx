import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useApi } from "../hooks/useApi";
import { useTheme } from "../theme";
import type { ForecastOut } from "../api/types";
import { money, num } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

const LINE_COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ec4899", "#a855f7", "#84cc16", "#ef4444"];

export function ForecastCard({ className }: { className?: string }) {
  const state = useApi<ForecastOut>("/forecast?months=6");
  const { grid, axis } = useTheme();

  return (
    <Card title="Net worth forecast" className={className}>
      <Async state={state}>
        {(f) => {
          // Merge all series into one row per month: { month, total, <accountId>: value, ... }
          const months = f.points.map((p) => p.month);
          const data = months.map((m, i) => {
            const row: Record<string, number | string> = { month: m };
            for (const s of f.series) row[s.key] = num(s.points[i]?.projected ?? 0);
            if (f.series.length === 0) row["total"] = num(f.points[i]?.projected ?? 0);
            return row;
          });
          const accountSeries = f.series.filter((s) => s.key !== "total");
          const labelFor: Record<string, string> = { total: "Total" };
          for (const s of f.series) labelFor[s.key] = s.label;

          return (
            <>
              <div className="metric-row">
                <div className="metric-block">
                  <div className="label">Now</div>
                  <div className="value">{money(f.current_total, f.base_currency)}</div>
                </div>
                <div className="metric-block">
                  <div className="label">Monthly net</div>
                  <div className={"value " + (num(f.monthly_net) >= 0 ? "pos" : "neg")}>
                    {money(f.monthly_net, f.base_currency)}
                  </div>
                </div>
              </div>
              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                  <defs>
                    <linearGradient id="fcFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#0891b2" stopOpacity={0.32} />
                      <stop offset="100%" stopColor="#0891b2" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={grid} />
                  <XAxis dataKey="month" tick={{ fill: axis, fontSize: 12 }} stroke={grid} />
                  <YAxis tick={{ fill: axis, fontSize: 12 }} stroke={grid} width={72}
                    tickFormatter={(v) => money(v)} />
                  <Tooltip
                    formatter={(v: number, key: string) => [money(v), labelFor[key] ?? key]}
                    contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, color: "var(--text)" }} />
                  {accountSeries.length > 0 && <Legend wrapperStyle={{ fontSize: 12 }} />}
                  <Area type="monotone" dataKey="total" name="Total" stroke="#0891b2"
                    strokeWidth={2.5} fill="url(#fcFill)" />
                  {accountSeries.map((s, i) => (
                    <Line key={s.key} type="monotone" dataKey={s.key} name={s.label}
                      stroke={LINE_COLORS[i % LINE_COLORS.length]} strokeWidth={1.6} dot={false} />
                  ))}
                </ComposedChart>
              </ResponsiveContainer>
              <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                {accountSeries.length > 0
                  ? "Total = account growth + your recent monthly net. Per-account lines show each balance compounding at its return."
                  : `Projected from your recent monthly net (${money(f.monthly_net)}/mo). Set a balance + return on an account to see per-account lines.`}{" "}
                Not advice.
              </div>
            </>
          );
        }}
      </Async>
    </Card>
  );
}
