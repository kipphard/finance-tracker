import { useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useApi } from "../hooks/useApi";
import { useTheme } from "../theme";
import type { CashEventOut, CashflowCalendarOut } from "../api/types";
import { money, num, shortDate } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

const KIND_ICON: Record<string, string> = {
  cashflow_item: "🔁",
  recurring_txn: "🔁",
  invoice: "📄",
  planned_save: "🎯",
  debt: "💳",
  tax: "🏛",
};

function EventTooltip({ active, payload }: { active?: boolean; payload?: any[] }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload as { date: string; balance: number; events: CashEventOut[] };
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, color: "var(--text)", padding: "8px 10px", fontSize: 12, maxWidth: 240 }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{shortDate(row.date)}</div>
      <div className="muted">Balance: {money(row.balance)}</div>
      {row.events?.map((e, i) => (
        <div key={i} style={{ marginTop: 3 }}>
          {KIND_ICON[e.kind] ?? "•"} {e.label}{" "}
          <span className={num(e.amount) >= 0 ? "pos" : "neg"}>{money(e.amount)}</span>
        </div>
      ))}
    </div>
  );
}

// Day-by-day projection of dated cash events + the running liquid balance for the next 60–90
// days. The dated counterpart to the (smooth) net-worth forecast: it flags the tightest day.
export function CashflowCalendarCard({ className }: { className?: string }) {
  const [days, setDays] = useState<60 | 90>(90);
  const state = useApi<CashflowCalendarOut>(`/reports/cashflow-calendar?days=${days}`);
  const { grid, axis } = useTheme();

  return (
    <Card title="Cashflow calendar" className={className}>
      <Async state={state}>
        {(c) => {
          const data = c.days.map((d) => ({
            date: d.date,
            balance: num(d.balance),
            events: d.events,
          }));
          const negative = c.first_negative_date != null;
          const tightColor = num(c.min_balance) < 0 ? "#ef4444" : "#f59e0b";
          return (
            <>
              <div className="metric-row">
                <div className="metric-block">
                  <div className="label">Today</div>
                  <div className="value">{money(c.start_balance, c.currency)}</div>
                </div>
                <div className="metric-block">
                  <div className="label">Tightest day</div>
                  <div className={"value " + (num(c.min_balance) < 0 ? "neg" : "")}>
                    {money(c.min_balance, c.currency)}
                  </div>
                </div>
                <div className="metric-block">
                  <div className="label">In / out ({days}d)</div>
                  <div className="value">
                    <span className="pos">{money(c.total_inflow)}</span>
                    {" / "}
                    <span className="neg">{money(c.total_outflow)}</span>
                  </div>
                </div>
              </div>

              <div style={{ display: "inline-flex", border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden", margin: "4px 0 10px" }}>
                {([60, 90] as const).map((d) => (
                  <button key={d} type="button" onClick={() => setDays(d)}
                    style={{
                      background: days === d ? "#6366f1" : "transparent",
                      color: days === d ? "#fff" : "var(--muted)",
                      border: 0, padding: "5px 14px", fontSize: 12, cursor: "pointer", fontWeight: 600,
                    }}>
                    {d}d
                  </button>
                ))}
              </div>

              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                  <defs>
                    <linearGradient id="ccFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#6366f1" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={grid} />
                  <XAxis dataKey="date" tick={{ fill: axis, fontSize: 11 }} stroke={grid}
                    tickFormatter={(v) => shortDate(v)} minTickGap={40} />
                  <YAxis tick={{ fill: axis, fontSize: 12 }} stroke={grid} width={72}
                    tickFormatter={(v) => money(v)} />
                  <Tooltip content={<EventTooltip />} />
                  <ReferenceLine y={0} stroke="#ef4444" strokeDasharray="4 4" />
                  {c.min_balance_date && (
                    <ReferenceLine x={c.min_balance_date} stroke={tightColor} strokeDasharray="2 2"
                      label={{ value: "tightest", fill: tightColor, fontSize: 10, position: "top" }} />
                  )}
                  <Area type="monotone" dataKey="balance" name="Balance" stroke="#6366f1"
                    strokeWidth={2.5} fill="url(#ccFill)" dot={false} />
                </ComposedChart>
              </ResponsiveContainer>

              <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                {negative
                  ? `⚠ Projected to go negative on ${shortDate(c.first_negative_date)}.`
                  : "Projected liquid balance from dated events (recurring items, invoice due dates, planned saves, debts, tax payments)."}{" "}
                Known dated events only — not the smooth forecast.
              </div>
            </>
          );
        }}
      </Async>
    </Card>
  );
}
