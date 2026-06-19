import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useApi } from "../hooks/useApi";
import type { ForecastOut } from "../api/types";
import { money, num } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

export function ForecastCard() {
  const state = useApi<ForecastOut>("/forecast?months=6");
  return (
    <Card title="Net worth forecast">
      <Async state={state}>
        {(f) => {
          const data = f.points.map((p) => ({
            month: p.month,
            projected: num(p.projected),
          }));
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
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef0f6" />
                  <XAxis dataKey="month" fontSize={11} />
                  <YAxis fontSize={11} width={72} tickFormatter={(v) => money(v)} />
                  <Tooltip formatter={(v: number) => money(v)} />
                  <Line type="monotone" dataKey="projected" stroke="#0891b2" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
              <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                Projected from recurring cashflow ({money(f.monthly_net)}/mo). Not advice.
              </div>
            </>
          );
        }}
      </Async>
    </Card>
  );
}
