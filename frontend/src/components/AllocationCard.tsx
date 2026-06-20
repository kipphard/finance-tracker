import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiDelete, apiPatch, apiPost } from "../api/client";
import type { AllocationPlanOut } from "../api/types";
import { money, num } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

const COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#06b6d4", "#a855f7", "#ec4899", "#84cc16"];

export function AllocationCard({ className }: { className?: string }) {
  const state = useApi<AllocationPlanOut>("/allocations/plan");
  const [name, setName] = useState("");
  const [percent, setPercent] = useState("");
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const clearDraft = (id: string) =>
    setDraft((d) => {
      const next = { ...d };
      delete next[id];
      return next;
    });

  const add = async () => {
    if (!name.trim() || !percent) return;
    setBusy(true);
    try {
      await apiPost("/allocations", { name: name.trim(), percent });
      setName("");
      setPercent("");
      state.reload();
    } finally {
      setBusy(false);
    }
  };

  const commitPercent = async (id: string, current: string) => {
    const v = draft[id];
    if (v == null || v === "" || num(v) === num(current)) {
      clearDraft(id);
      return;
    }
    await apiPatch(`/allocations/${id}`, { percent: v });
    clearDraft(id);
    state.reload();
  };

  const remove = async (id: string) => {
    await apiDelete(`/allocations/${id}`);
    state.reload();
  };

  return (
    <Card title="Distribute leftover" className={className}>
      <Async state={state}>
        {(plan) => {
          const leftover = num(plan.leftover);
          const totalPct = num(plan.allocated_percent);
          const denom = Math.max(100, totalPct);
          const over = totalPct > 100;

          if (leftover <= 0) {
            return (
              <div className="empty">
                Add your recurring income and fixed costs in the <b>Monthly cashflow</b> card,
                then split what's left here.
              </div>
            );
          }

          return (
            <>
              <div className="muted" style={{ fontSize: 12 }}>
                {money(plan.monthly_income, plan.currency)} income −{" "}
                {money(plan.monthly_fixed, plan.currency)} fixed costs
              </div>
              <div className="alloc__leftover">
                {money(plan.leftover, plan.currency)}{" "}
                <span className="muted" style={{ fontSize: 12, fontWeight: 400 }}>left / month</span>
              </div>

              {plan.buckets.length > 0 && (
                <div className="alloc__bar">
                  {plan.buckets.map((b, i) => (
                    <div
                      key={b.id}
                      className="alloc__seg"
                      style={{ width: `${(num(b.percent) / denom) * 100}%`, background: COLORS[i % COLORS.length] }}
                      title={`${b.name} · ${num(b.percent)}%`}
                    />
                  ))}
                  {!over && totalPct < 100 && (
                    <div className="alloc__seg alloc__seg--rest" style={{ width: `${((100 - totalPct) / denom) * 100}%` }} />
                  )}
                </div>
              )}

              {plan.buckets.length === 0 ? (
                <div className="empty">
                  Add buckets to split {money(plan.leftover, plan.currency)} — e.g. Savings 50%,
                  Invest 30%, Buffer 20%.
                </div>
              ) : (
                <ul className="list">
                  {plan.buckets.map((b, i) => (
                    <li key={b.id}>
                      <span className="li-main">
                        <span className="alloc__dot" style={{ background: COLORS[i % COLORS.length] }} />
                        {b.name}
                      </span>
                      <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <input
                          className="input alloc__pct"
                          type="number"
                          min="0"
                          max="100"
                          step="0.5"
                          value={draft[b.id] ?? String(num(b.percent))}
                          onChange={(e) => setDraft((d) => ({ ...d, [b.id]: e.target.value }))}
                          onBlur={() => commitPercent(b.id, b.percent)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                          }}
                        />
                        <span className="muted">%</span>
                        <strong style={{ minWidth: 78, textAlign: "right" }}>
                          {money(b.amount, plan.currency)}
                        </strong>
                        <button className="btn btn--ghost" style={{ padding: "0 6px" }}
                          onClick={() => remove(b.id)} title="Remove">×</button>
                      </span>
                    </li>
                  ))}
                  {over ? (
                    <li>
                      <span className="li-main neg">⚠ Over 100% — reduce a bucket</span>
                      <span className="neg">{totalPct}%</span>
                    </li>
                  ) : totalPct < 100 ? (
                    <li style={{ opacity: 0.75 }}>
                      <span className="li-main muted">Unallocated · {num(plan.unallocated_percent)}%</span>
                      <span className="muted">{money(plan.unallocated_amount, plan.currency)}</span>
                    </li>
                  ) : null}
                </ul>
              )}

              <div className="toolbar" style={{ marginTop: 12 }}>
                <input className="input" placeholder="Bucket (e.g. Savings)" value={name}
                  onChange={(e) => setName(e.target.value)} />
                <input className="input" type="number" min="0" max="100" step="0.5" placeholder="%"
                  value={percent} onChange={(e) => setPercent(e.target.value)} style={{ width: 80 }} />
                <button className="btn" onClick={add} disabled={busy || !name.trim() || !percent}>Add</button>
              </div>
            </>
          );
        }}
      </Async>
    </Card>
  );
}
