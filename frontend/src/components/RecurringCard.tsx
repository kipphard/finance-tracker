import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiPost } from "../api/client";
import type { RecurringOut } from "../api/types";
import { money, num, shortDate } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

export function RecurringCard() {
  const state = useApi<RecurringOut[]>("/recurring");
  const [busy, setBusy] = useState(false);

  const detect = async () => {
    setBusy(true);
    try {
      await apiPost("/recurring/detect");
      state.reload();
    } finally {
      setBusy(false);
    }
  };

  const action = (
    <button className="btn btn--ghost" onClick={detect} disabled={busy}>
      {busy ? "…" : "Detect"}
    </button>
  );

  return (
    <Card title="Upcoming & recurring" action={action}>
      <Async state={state}>
        {(items) =>
          items.length === 0 ? (
            <div className="empty">
              None detected yet. Import transactions, then hit Detect.
            </div>
          ) : (
            <ul className="list">
              {items.map((r) => (
                <li key={r.id}>
                  <span>
                    <span className="li-main">{r.payee}</span>{" "}
                    <span className="li-sub">
                      · {r.cadence} · next {shortDate(r.next_due)}
                    </span>
                  </span>
                  <span className={"amount " + (num(r.amount_est) >= 0 ? "pos" : "neg")}>
                    {money(r.amount_est)}
                  </span>
                </li>
              ))}
            </ul>
          )
        }
      </Async>
    </Card>
  );
}
