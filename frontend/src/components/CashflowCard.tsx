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
import type { CashflowItemOut, CashflowSummaryOut } from "../api/types";
import { money, num } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

export function CashflowCard() {
  const summary = useApi<CashflowSummaryOut>("/cashflow/summary");
  const items = useApi<CashflowItemOut[]>("/cashflow");

  return (
    <Card title="Monthly cashflow">
      <Async state={summary}>
        {(s) => (
          <>
            <div className="metric-row">
              <div className="metric-block">
                <div className="label">Inflow</div>
                <div className="value pos">{money(s.monthly_inflow, s.currency)}</div>
              </div>
              <div className="metric-block">
                <div className="label">Outflow</div>
                <div className="value neg">{money(s.monthly_outflow, s.currency)}</div>
              </div>
              <div className="metric-block">
                <div className="label">Net</div>
                <div className={"value " + (num(s.monthly_net) >= 0 ? "pos" : "neg")}>
                  {money(s.monthly_net, s.currency)}
                </div>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={130}>
              <BarChart
                data={[
                  {
                    name: "per month",
                    Inflow: num(s.monthly_inflow),
                    Outflow: num(s.monthly_outflow),
                  },
                ]}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#eef0f6" />
                <XAxis dataKey="name" fontSize={11} />
                <YAxis fontSize={11} width={64} tickFormatter={(v) => money(v)} />
                <Tooltip formatter={(v: number) => money(v)} />
                <Legend />
                <Bar dataKey="Inflow" fill="#16a34a" />
                <Bar dataKey="Outflow" fill="#c0392b" />
              </BarChart>
            </ResponsiveContainer>
          </>
        )}
      </Async>

      <Async state={items}>
        {(list) => {
          const active = list.filter((i) => i.active);
          if (active.length === 0)
            return <div className="empty">No recurring items yet (add via /api/cashflow).</div>;
          return (
            <ul className="list" style={{ marginTop: 12 }}>
              {active.map((i) => (
                <li key={i.id}>
                  <span>
                    <span className="li-main">{i.name}</span>{" "}
                    <span className="li-sub">· {i.cadence}</span>
                  </span>
                  <span className={"amount " + (i.direction === "inflow" ? "pos" : "neg")}>
                    {i.direction === "inflow" ? "+" : "−"}
                    {money(i.amount, i.currency)}
                  </span>
                </li>
              ))}
            </ul>
          );
        }}
      </Async>
    </Card>
  );
}
