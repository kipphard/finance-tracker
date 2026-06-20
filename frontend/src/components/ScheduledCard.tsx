import { useApi } from "../hooks/useApi";
import { apiDelete } from "../api/client";
import type { CashflowItemOut } from "../api/types";
import { money, shortDate, titleCase } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

export function ScheduledCard({ className }: { className?: string }) {
  const state = useApi<CashflowItemOut[]>("/cashflow");

  const stop = async (id: string) => {
    await apiDelete(`/cashflow/${id}`);
    state.reload();
  };

  return (
    <Card title="Scheduled (auto-repeats)" className={className}>
      <Async state={state}>
        {(items) => {
          // All active recurring items. Those with a target account auto-post transactions;
          // those without still count toward the monthly plan (income / fixed costs), so we
          // show them here too — otherwise they'd silently skew the numbers while staying hidden.
          const templates = items.filter((i) => i.active && i.cadence !== "one_off");
          if (templates.length === 0)
            return (
              <div className="empty">
                Nothing scheduled. Tick "Repeat" when adding a transaction and it'll post
                automatically.
              </div>
            );
          return (
            <ul className="list">
              {templates.map((t) => (
                <li key={t.id}>
                  <span>
                    <span className="li-main">{t.name}</span>{" "}
                    <span className="li-sub">
                      · {titleCase(t.cadence)} ·{" "}
                      {t.account_id ? `next ${shortDate(t.next_due)}` : "budget only"}
                    </span>
                  </span>
                  <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span className={"tnum " + (t.direction === "inflow" ? "pos" : "neg")}>
                      {t.direction === "inflow" ? "+" : "−"}
                      {money(t.amount, t.currency)}
                    </span>
                    <button className="btn btn--ghost btn--sm" style={{ padding: "2px 7px" }}
                      onClick={() => stop(t.id)} title="Stop repeating">
                      ×
                    </button>
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
