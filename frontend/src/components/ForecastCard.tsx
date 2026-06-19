import {
  Area,
  AreaChart,
  CartesianGrid,
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

export function ForecastCard({ className }: { className?: string }) {
  const state = useApi<ForecastOut>("/forecast?months=6");
  const { grid, axis } = useTheme();

  return (
    <Card title="Net worth forecast" className={className}>
      <Async state={state}>
        {(f) => {
          const data = f.points.map((p) => ({ month: p.month, projected: num(p.projected) }));
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
                <AreaChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
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
                  <Tooltip formatter={(v: number) => money(v)}
                    contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, color: "var(--text)" }} />
                  <Area type="monotone" dataKey="projected" stroke="#0891b2" strokeWidth={2.5} fill="url(#fcFill)" />
                </AreaChart>
              </ResponsiveContainer>
              <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                Projected from your recent monthly net ({money(f.monthly_net)}/mo). Not advice.
              </div>
            </>
          );
        }}
      </Async>
    </Card>
  );
}
