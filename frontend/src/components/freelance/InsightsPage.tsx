import { useApi } from "../../hooks/useApi";
import type { FreelanceInsightsOut } from "../../api/types";
import { money, num } from "../../lib/format";
import { Card } from "../Card";
import { Async } from "../Async";
import { fmtHours } from "./helpers";

export function InsightsPage() {
  const state = useApi<FreelanceInsightsOut>("/reports/freelance-insights");

  return (
    <div className="card-stack">
      <Card title="Client profitability" className="recurring-card">
        <Async state={state}>
          {(ins) => ins.clients.length === 0 ? (
            <div className="empty">No clients yet.</div>
          ) : (
            <div className="table-scroll">
            <table className="ftable">
              <thead>
                <tr>
                  <th>Client</th>
                  <th className="ftable__num">Effective €/h</th>
                  <th className="ftable__num">Tracked</th>
                  <th className="ftable__num">Billed</th>
                  <th className="ftable__num">Unbilled</th>
                  <th className="ftable__num">Invoiced</th>
                  <th className="ftable__num">Paid</th>
                </tr>
              </thead>
              <tbody>
                {ins.clients.map((c) => (
                  <tr key={c.client_id}>
                    <td>{c.name}</td>
                    <td className="ftable__num tnum"><strong>{money(c.effective_rate)}</strong></td>
                    <td className="ftable__num tnum">{fmtHours(c.tracked_hours)}</td>
                    <td className="ftable__num tnum">{fmtHours(c.billed_hours)}</td>
                    <td className="ftable__num tnum">{fmtHours(c.unbilled_hours)}</td>
                    <td className="ftable__num tnum">{money(c.invoiced_total)}</td>
                    <td className="ftable__num tnum">{money(c.paid_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}
        </Async>
        <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          Effective €/h = total invoiced ÷ total tracked hours (includes flat fees; counts hours not
          yet billed, so it rises as you invoice unbilled time).
        </div>
      </Card>

      <Card title="Project budgets — burn-down">
        <Async state={state}>
          {(ins) => ins.projects.length === 0 ? (
            <div className="empty">No projects with an hour budget. Set a budget on a project to track burn-down.</div>
          ) : (
            <div className="burn-list">
              {ins.projects.map((p) => {
                const pct = num(p.pct);
                const cls = pct >= 100 ? " is-over" : pct >= 80 ? " is-warn" : "";
                return (
                  <div key={p.project_id} className="burn-row">
                    <div className="burn-row__head">
                      <span>
                        <strong>{p.name}</strong>
                        {p.client_name ? <span className="muted"> · {p.client_name}</span> : null}
                        {p.over_budget && (
                          <span className="badge badge--recurring" style={{ marginLeft: 6 }}>über Budget</span>
                        )}
                      </span>
                      <span className="tnum">{fmtHours(p.tracked_hours)} / {fmtHours(p.budget_hours)}</span>
                    </div>
                    <div className="progress">
                      <div className={"progress__bar" + cls} style={{ width: `${Math.min(100, pct)}%` }} />
                    </div>
                    <div className="muted" style={{ fontSize: 11, marginTop: 3 }}>
                      {p.over_budget
                        ? `${fmtHours(String(Math.abs(num(p.remaining_hours))))} über Budget`
                        : `${fmtHours(p.remaining_hours)} verbleibend`}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Async>
      </Card>
    </div>
  );
}
