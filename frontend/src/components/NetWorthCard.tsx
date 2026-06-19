import { useApi } from "../hooks/useApi";
import type { NetWorthOut } from "../api/types";
import { money } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

export function NetWorthCard() {
  const state = useApi<NetWorthOut>("/networth");
  return (
    <Card title="Net worth">
      <Async state={state}>
        {(nw) => (
          <>
            <div className="metric">{money(nw.total, nw.base_currency)}</div>
            <div className="chips" style={{ margin: "10px 0" }}>
              {Object.entries(nw.by_currency).map(([cur, amt]) => (
                <span className="chip" key={cur}>
                  {money(amt, cur)}
                </span>
              ))}
            </div>
            {nw.breakdown.length === 0 ? (
              <div className="empty">No accounts yet.</div>
            ) : (
              <ul className="list">
                {nw.breakdown.map((b) => (
                  <li key={b.account_id}>
                    <span>
                      <span className="li-main">{b.name}</span>{" "}
                      <span className="li-sub">· {b.connector}</span>
                    </span>
                    <span className="amount">{money(b.amount, b.currency)}</span>
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
