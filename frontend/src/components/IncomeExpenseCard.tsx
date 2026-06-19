import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiDownload } from "../api/client";
import type { IncomeExpenseReport } from "../api/types";
import { money, num } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

function yearStart(): string {
  return new Date().toISOString().slice(0, 4) + "-01-01";
}
function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function IncomeExpenseCard({ className }: { className?: string }) {
  const [start, setStart] = useState(yearStart());
  const [end, setEnd] = useState(today());
  const state = useApi<IncomeExpenseReport>(
    `/reports/income-expense?start=${start}&end=${end}`,
  );

  const download = () =>
    apiDownload(
      `/reports/transactions.csv?start=${start}&end=${end}`,
      `transactions_${start}_${end}.csv`,
    );

  const action = (
    <button className="btn btn--sm" onClick={download}>
      ⬇ CSV
    </button>
  );

  return (
    <Card title="Income & expenses" className={className} action={action}>
      <div className="toolbar">
        <div className="field" style={{ flex: 1 }}>
          <label>From</label>
          <input className="input" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </div>
        <div className="field" style={{ flex: 1 }}>
          <label>To</label>
          <input className="input" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </div>
      </div>

      <Async state={state}>
        {(r) => (
          <>
            <div className="metric-row">
              <div className="metric-block">
                <div className="label">Income</div>
                <div className="value pos">{money(r.income)}</div>
              </div>
              <div className="metric-block">
                <div className="label">Expenses</div>
                <div className="value neg">{money(r.expense)}</div>
              </div>
              <div className="metric-block">
                <div className="label">Net</div>
                <div className={"value " + (num(r.net) >= 0 ? "pos" : "neg")}>{money(r.net)}</div>
              </div>
            </div>
            {r.by_category.length === 0 ? (
              <div className="empty">No transactions in this range.</div>
            ) : (
              <ul className="list">
                {r.by_category.map((c, i) => (
                  <li key={i}>
                    <span>
                      <span className="li-main">{c.name}</span>{" "}
                      <span className="li-sub">· {c.count}</span>
                    </span>
                    <span className={"tnum " + (num(c.total) >= 0 ? "pos" : "neg")}>
                      {money(c.total)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Async>
    </Card>
  );
}
