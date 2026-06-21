import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiDelete, apiPost } from "../api/client";
import type { PlannedPurchaseOut, PlannedPurchasesOut } from "../api/types";
import { money } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

function whenLabel(item: PlannedPurchaseOut, currency: string): { text: string; cls: string } {
  if (item.affordable_now) return { text: "✅ Affordable now", cls: "pos" };
  if (item.months == null)
    return { text: "Set income & allocation to plan this", cls: "muted" };
  const by = item.target_month
    ? new Date(item.target_month).toLocaleDateString(undefined, { month: "short", year: "numeric" })
    : null;
  const n = item.months;
  return {
    text: `in ~${n} ${n === 1 ? "month" : "months"}${by ? ` · by ${by}` : ""}`,
    cls: "",
  };
}

export function PlannedPurchasesCard({ className }: { className?: string }) {
  const state = useApi<PlannedPurchasesOut>("/planned-purchases");
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [busy, setBusy] = useState(false);

  const add = async () => {
    if (!name.trim() || !price) return;
    setBusy(true);
    try {
      await apiPost("/planned-purchases", { name: name.trim(), price });
      setName("");
      setPrice("");
      state.reload();
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    await apiDelete(`/planned-purchases/${id}`);
    state.reload();
  };

  return (
    <Card title="Planned purchases" className={className}>
      <Async state={state}>
        {(plan) => (
          <>
            <div className="muted" style={{ fontSize: 12 }}>
              {Number(plan.monthly_budget) > 0 ? (
                <>
                  ~{money(plan.monthly_budget, plan.currency)}/month free to save{" "}
                  <span style={{ opacity: 0.7 }}>(after debt, emergency fund &amp; investing)</span>
                </>
              ) : (
                <>No money free to save yet — set income, fixed costs &amp; allocation first.</>
              )}
            </div>

            <ul className="list" style={{ marginTop: 10 }}>
              {plan.items.map((item) => {
                const w = whenLabel(item, plan.currency);
                return (
                  <li key={item.id}>
                    <span className="li-main">
                      {item.name}{" "}
                      <span className="muted" style={{ fontWeight: 400 }}>
                        · {money(item.price, plan.currency)}
                      </span>
                    </span>
                    <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span className={w.cls} style={{ fontSize: 13 }}>
                        {w.text}
                      </span>
                      <button
                        className="btn btn--ghost"
                        style={{ padding: "0 6px" }}
                        onClick={() => remove(item.id)}
                        title="Remove"
                      >
                        ×
                      </button>
                    </span>
                  </li>
                );
              })}
              {plan.items.length === 0 && (
                <li className="muted" style={{ justifyContent: "center" }}>
                  Add something you're saving up for ✨
                </li>
              )}
            </ul>

            <div className="toolbar" style={{ marginTop: 12 }}>
              <input
                className="input"
                placeholder="Item (e.g. Nintendo Switch 2)"
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && add()}
              />
              <input
                className="input"
                type="number"
                min="0"
                step="0.01"
                placeholder="Price"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && add()}
                style={{ width: 100 }}
              />
              <button className="btn" onClick={add} disabled={busy || !name.trim() || !price}>
                Add
              </button>
            </div>
          </>
        )}
      </Async>
    </Card>
  );
}
