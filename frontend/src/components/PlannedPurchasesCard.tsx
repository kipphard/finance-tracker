import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiDelete, apiPatch, apiPost } from "../api/client";
import type { AccountOut, PlannedPurchaseOut, PlannedPurchasesOut } from "../api/types";
import { money, num } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

function whenLabel(item: PlannedPurchaseOut): { text: string; cls: string } {
  if (item.months == null || num(item.monthly_save) <= 0)
    return { text: "set a monthly amount →", cls: "muted" };
  const by = item.target_month
    ? new Date(item.target_month).toLocaleDateString(undefined, { month: "short", year: "numeric" })
    : null;
  const n = item.months;
  if (n <= 1) return { text: `ready next month${by ? ` · ${by}` : ""}`, cls: "pos" };
  return { text: `in ~${n} months${by ? ` · by ${by}` : ""}`, cls: "" };
}

export function PlannedPurchasesCard({ className }: { className?: string }) {
  const state = useApi<PlannedPurchasesOut>("/planned-purchases");
  const accounts = useApi<AccountOut[]>("/accounts");
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [draft, setDraft] = useState<Record<string, string>>({});
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

  const commitSave = async (item: PlannedPurchaseOut) => {
    const v = draft[item.id];
    if (v == null || num(v) === num(item.monthly_save)) {
      setDraft((d) => {
        const next = { ...d };
        delete next[item.id];
        return next;
      });
      return;
    }
    await apiPatch(`/planned-purchases/${item.id}`, { monthly_save: v || "0" });
    setDraft((d) => {
      const next = { ...d };
      delete next[item.id];
      return next;
    });
    state.reload();
  };

  const remove = async (id: string) => {
    await apiDelete(`/planned-purchases/${id}`);
    state.reload();
  };

  const patchItem = async (id: string, body: Record<string, unknown>) => {
    await apiPatch(`/planned-purchases/${id}`, body);
    state.reload();
  };

  return (
    <Card title="Planned purchases" className={className}>
      <Async state={state}>
        {(plan) => (
          <>
            <div className="muted" style={{ fontSize: 12 }}>
              {num(plan.planned_fund) > 0 ? (
                <>
                  Saving <b>{money(plan.planned_fund, plan.currency)}/month</b> toward your wishlist
                  <span style={{ opacity: 0.7 }}> — shows up as a pot in Distribute leftover.</span>
                </>
              ) : (
                <>Set a monthly amount per item to see when you can buy it.</>
              )}
            </div>

            <ul className="list" style={{ marginTop: 10 }}>
              {plan.items.map((item) => {
                const w = whenLabel(item);
                return (
                  <li key={item.id} style={{ display: "block" }}>
                    <div
                      style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
                    >
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
                    </div>
                    <div
                      className="alloc__tick"
                      style={{ marginTop: 6, display: "flex", alignItems: "center", gap: 6 }}
                    >
                      <span className="muted" style={{ fontSize: 11 }}>
                        save / month
                      </span>
                      <input
                        className="input alloc__amt"
                        type="number"
                        min="0"
                        step="10"
                        value={draft[item.id] ?? String(num(item.monthly_save) || "")}
                        placeholder="0"
                        onChange={(e) => setDraft((d) => ({ ...d, [item.id]: e.target.value }))}
                        onBlur={() => commitSave(item)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                        }}
                      />
                      <span className="muted">€</span>
                      <select className="select" style={{ maxWidth: 120, fontSize: 12, marginLeft: "auto" }}
                        value={item.account_id ?? ""}
                        onChange={(e) => patchItem(item.id, { account_id: e.target.value || null })}
                        title="Savings account — 'Apply this month' transfers the monthly amount into it">
                        <option value="">no account</option>
                        {(accounts.data ?? []).map((a) => (
                          <option key={a.id} value={a.id}>→ {a.name}</option>
                        ))}
                      </select>
                      {item.account_id && (
                        <label className="muted" style={{ display: "flex", alignItems: "center", gap: 2, fontSize: 11 }}
                          title="Exclude this account from cash runway">
                          <input type="checkbox" checked={item.earmarked}
                            onChange={(e) => patchItem(item.id, { earmarked: e.target.checked })} />
                          🔒
                        </label>
                      )}
                    </div>
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
