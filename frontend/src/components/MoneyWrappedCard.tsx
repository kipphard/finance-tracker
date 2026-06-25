import { useState } from "react";
import { useApi } from "../hooks/useApi";
import type { WrappedOut } from "../api/types";
import { money, num } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

const NOW = new Date().getFullYear();
const YEARS = [NOW, NOW - 1, NOW - 2, NOW - 3];

function monthLabel(ym: string | null): string {
  if (!ym) return "—";
  const [y, m] = ym.split("-").map(Number);
  if (!y || !m) return ym;
  return new Date(y, m - 1, 1).toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

export function MoneyWrappedCard({ className }: { className?: string }) {
  const [year, setYear] = useState(NOW);
  const state = useApi<WrappedOut>(`/reports/wrapped?year=${year}`);

  const action = (
    <select className="select" style={{ maxWidth: 110 }} value={year}
      onChange={(e) => setYear(Number(e.target.value))}>
      {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
    </select>
  );

  return (
    <Card title="💸 Money Wrapped" className={className} action={action}>
      <Async state={state}>
        {(w) =>
          !w.has_data ? (
            <div className="empty">No activity recorded for {w.year} yet.</div>
          ) : (
            <>
              <div className="metric-row">
                <div className="metric-block">
                  <div className="label">Earned in {w.year}</div>
                  <div className="value pos">{money(w.total_income, w.currency)}</div>
                </div>
                <div className="metric-block">
                  <div className="label">Spent</div>
                  <div className="value neg">{money(w.total_expense, w.currency)}</div>
                </div>
                <div className="metric-block">
                  <div className="label">Net</div>
                  <div className={"value " + (num(w.net) >= 0 ? "pos" : "neg")}>
                    {money(w.net, w.currency)}
                  </div>
                </div>
              </div>

              <div className="metric-row">
                <div className="metric-block">
                  <div className="label">Hours worked</div>
                  <div className="value">{num(w.hours_worked).toFixed(0)} h</div>
                </div>
                <div className="metric-block">
                  <div className="label">Invoices sent</div>
                  <div className="value">{w.invoices_count}</div>
                </div>
                {w.net_worth_delta != null && (
                  <div className="metric-block">
                    <div className="label">Net-worth change</div>
                    <div className={"value " + (num(w.net_worth_delta) >= 0 ? "pos" : "neg")}>
                      {money(w.net_worth_delta, w.currency)}
                    </div>
                  </div>
                )}
              </div>

              <ul className="list" style={{ marginTop: 8 }}>
                {w.best_client_name && (
                  <li>
                    <span><span className="li-main">🏆 Best client</span> · {w.best_client_name}</span>
                    <span className="amount">{money(w.best_client_rate, w.currency)}/h</span>
                  </li>
                )}
                {w.priciest_month && (
                  <li>
                    <span><span className="li-main">📅 Priciest month</span> · {monthLabel(w.priciest_month)}</span>
                    <span className="amount neg">{money(w.priciest_month_amount, w.currency)}</span>
                  </li>
                )}
                {w.biggest_expense_payee && (
                  <li>
                    <span><span className="li-main">💥 Biggest expense</span> · {w.biggest_expense_payee}</span>
                    <span className="amount neg">{money(w.biggest_expense_amount, w.currency)}</span>
                  </li>
                )}
                {w.top_categories.map((c, i) => (
                  <li key={i}>
                    <span>
                      <span className="li-main">{i === 0 ? "🥇" : i === 1 ? "🥈" : "🥉"} Top category</span>
                      {" · "}{c.name}
                    </span>
                    <span className="amount neg">{money(c.amount, w.currency)}</span>
                  </li>
                ))}
              </ul>

              <div className="muted" style={{ fontSize: 11, marginTop: 8 }}>
                Your year in money, from the transactions, time and invoices you've tracked.
              </div>
            </>
          )
        }
      </Async>
    </Card>
  );
}
