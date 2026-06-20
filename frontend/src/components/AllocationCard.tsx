import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiDelete, apiPatch, apiPost } from "../api/client";
import type { AllocationPlanOut, DebtOut, EmergencyFundOut } from "../api/types";
import { money, num } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

const COLORS = ["#6366f1", "#10b981", "#f59e0b", "#06b6d4", "#a855f7", "#ec4899", "#84cc16"];
const DEBT_COLOR = "#ef4444";
const EF_COLOR = "#14b8a6";
const TICK_KEY = "ft_debt_payoff_ids";
const PAY_KEY = "ft_debt_pay_amounts";
const EF_KEY = "ft_ef_contribution";

function loadTicked(): string[] | null {
  try {
    const v = JSON.parse(localStorage.getItem(TICK_KEY) || "null");
    return Array.isArray(v) ? v : null;
  } catch {
    return null;
  }
}
function loadPay(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(PAY_KEY) || "{}") || {};
  } catch {
    return {};
  }
}

const isDebtBucket = (name: string) => name.trim().toLowerCase() === "debt";
const isEfBucket = (name: string) => name.trim().toLowerCase() === "emergency fund";

export function AllocationCard({ className }: { className?: string }) {
  const state = useApi<AllocationPlanOut>("/allocations/plan");
  const debtsApi = useApi<DebtOut[]>("/debts");
  const efApi = useApi<EmergencyFundOut>("/emergency-fund");
  const [name, setName] = useState("");
  const [percent, setPercent] = useState("");
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [payDraft, setPayDraft] = useState<Record<string, string>>(() => loadPay());
  const [tickedRaw, setTickedRaw] = useState<string[] | null>(() => loadTicked());
  const [efPay, setEfPay] = useState<string>(() => {
    try {
      return localStorage.getItem(EF_KEY) ?? "";
    } catch {
      return "";
    }
  });
  const [busy, setBusy] = useState(false);

  const saveEfPay = (v: string) => {
    setEfPay(v);
    try {
      localStorage.setItem(EF_KEY, v);
    } catch {
      /* ignore */
    }
  };

  const saveTicked = (ids: string[]) => {
    setTickedRaw(ids);
    try {
      localStorage.setItem(TICK_KEY, JSON.stringify(ids));
    } catch {
      /* ignore */
    }
  };
  const savePay = (next: Record<string, string>) => {
    setPayDraft(next);
    try {
      localStorage.setItem(PAY_KEY, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  };

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

  const addDebtBucket = async () => {
    setBusy(true);
    try {
      await apiPost("/allocations", { name: "Debt", percent: "1" });
      state.reload();
    } finally {
      setBusy(false);
    }
  };

  const addEfBucket = async () => {
    setBusy(true);
    try {
      await apiPost("/allocations", { name: "Emergency fund", percent: "1" });
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
          const gross = num(plan.leftover); // income − fixed costs
          if (gross <= 0) {
            return (
              <div className="empty">
                Add your recurring income and fixed costs in the <b>Monthly cashflow</b> card,
                then split what's left here.
              </div>
            );
          }

          const unpaidDebts = (debtsApi.data ?? []).filter((d) => !d.paid);
          const outstanding = unpaidDebts.reduce((s, d) => s + num(d.amount), 0);
          const tickedSet =
            tickedRaw !== null ? new Set(tickedRaw) : new Set(unpaidDebts.map((d) => d.id));
          const debtBucket = plan.buckets.find((b) => isDebtBucket(b.name));
          const efBucket = plan.buckets.find((b) => isEfBucket(b.name));
          const otherBuckets = plan.buckets.filter(
            (b) => !isDebtBucket(b.name) && !isEfBucket(b.name),
          );

          const amountFor = (d: DebtOut) => payDraft[d.id] ?? String(num(d.amount));
          // Debt + emergency fund are first claims taken off the top — not a % of the leftover.
          const debtPay = debtBucket
            ? unpaidDebts.filter((d) => tickedSet.has(d.id)).reduce((s, d) => s + num(amountFor(d)), 0)
            : 0;
          const tickedTotal = unpaidDebts
            .filter((d) => tickedSet.has(d.id))
            .reduce((s, d) => s + num(d.amount), 0);
          const months = debtPay > 0 && tickedTotal > 0 ? Math.ceil(tickedTotal / debtPay) : null;

          const ef = efApi.data;
          const efContribution = efBucket ? num(efPay) : 0;
          const efGap = ef ? num(ef.gap) : 0;
          const efMonths = efContribution > 0 && efGap > 0 ? Math.ceil(efGap / efContribution) : null;

          const distributable = Math.max(0, gross - debtPay - efContribution);
          const allocatedPct = otherBuckets.reduce((s, b) => s + num(b.percent), 0);
          const over = allocatedPct > 100;
          const denom = Math.max(100, allocatedPct);
          const unallocPct = Math.max(0, 100 - allocatedPct);
          const bucketAmt = (b: { percent: string }) => (num(b.percent) / 100) * distributable;

          return (
            <>
              <div className="muted" style={{ fontSize: 12 }}>
                {money(plan.monthly_income, plan.currency)} income −{" "}
                {money(plan.monthly_fixed, plan.currency)} fixed costs
                {debtPay > 0 ? ` − ${money(debtPay, plan.currency)} debt` : ""}
                {efContribution > 0 ? ` − ${money(efContribution, plan.currency)} emergency fund` : ""}
              </div>
              <div className="alloc__leftover">
                {money(distributable, plan.currency)}{" "}
                <span className="muted" style={{ fontSize: 12, fontWeight: 400 }}>to distribute</span>
              </div>

              {otherBuckets.length > 0 && (
                <div className="alloc__bar">
                  {otherBuckets.map((b, i) => (
                    <div
                      key={b.id}
                      className="alloc__seg"
                      style={{ width: `${(num(b.percent) / denom) * 100}%`, background: COLORS[i % COLORS.length] }}
                      title={`${b.name} · ${num(b.percent)}%`}
                    />
                  ))}
                  {!over && unallocPct > 0 && (
                    <div className="alloc__seg alloc__seg--rest" style={{ width: `${(unallocPct / denom) * 100}%` }} />
                  )}
                </div>
              )}

              <ul className="list">
                {/* Debt — always first, taken off the top */}
                {debtBucket && (
                  <li style={{ display: "block" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span className="li-main">
                        <span className="alloc__dot" style={{ background: DEBT_COLOR }} />
                        🎯 Debt <span className="muted" style={{ fontWeight: 400 }}>· off the top</span>
                      </span>
                      <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <strong style={{ minWidth: 78, textAlign: "right" }}>
                          {money(debtPay, plan.currency)}
                        </strong>
                        <button className="btn btn--ghost" style={{ padding: "0 6px" }}
                          onClick={() => remove(debtBucket.id)} title="Remove">×</button>
                      </span>
                    </div>
                    {unpaidDebts.length === 0 ? (
                      <div className="li-sub" style={{ marginTop: 6 }}>No open debt 🎉</div>
                    ) : (
                      <div className="alloc__debt">
                        <div className="alloc__debtlist">
                          {unpaidDebts.map((d) => {
                            const checked = tickedSet.has(d.id);
                            return (
                              <div key={d.id} className="alloc__tick">
                                <input type="checkbox" checked={checked}
                                  onChange={(e) => {
                                    const next = new Set(tickedSet);
                                    if (e.target.checked) next.add(d.id);
                                    else next.delete(d.id);
                                    saveTicked([...next]);
                                  }} />
                                <span>
                                  {d.name} <span className="muted">· {money(d.amount)}</span>
                                </span>
                                {checked && (
                                  <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
                                    <span className="muted" style={{ fontSize: 11 }}>pay</span>
                                    <input
                                      className="input alloc__amt"
                                      type="number"
                                      min="0"
                                      step="0.01"
                                      value={amountFor(d)}
                                      onChange={(e) => savePay({ ...payDraft, [d.id]: e.target.value })}
                                    />
                                    <span className="muted">€</span>
                                  </span>
                                )}
                              </div>
                            );
                          })}
                        </div>
                        <div className="li-sub" style={{ marginTop: 6 }}>
                          {months != null
                            ? `${money(debtPay, plan.currency)}/mo → clears ${money(tickedTotal, plan.currency)} in ~${months} ${months === 1 ? "month" : "months"}`
                            : "Tick a debt and enter how much you're paying."}
                        </div>
                      </div>
                    )}
                  </li>
                )}

                {/* Emergency fund — also off the top */}
                {efBucket && (
                  <li style={{ display: "block" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span className="li-main">
                        <span className="alloc__dot" style={{ background: EF_COLOR }} />
                        💰 Emergency fund <span className="muted" style={{ fontWeight: 400 }}>· off the top</span>
                      </span>
                      <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <strong style={{ minWidth: 78, textAlign: "right" }}>
                          {money(efContribution, plan.currency)}
                        </strong>
                        <button className="btn btn--ghost" style={{ padding: "0 6px" }}
                          onClick={() => remove(efBucket.id)} title="Remove">×</button>
                      </span>
                    </div>
                    {ef && efGap <= 0 ? (
                      <div className="li-sub" style={{ marginTop: 6 }}>Fully funded 🎉</div>
                    ) : (
                      <div className="alloc__debt">
                        <div className="alloc__tick">
                          <span className="muted" style={{ fontSize: 11 }}>put / month</span>
                          <input
                            className="input alloc__amt"
                            style={{ marginLeft: "auto" }}
                            type="number"
                            min="0"
                            step="0.01"
                            value={efPay}
                            onChange={(e) => saveEfPay(e.target.value)}
                          />
                          <span className="muted">€</span>
                        </div>
                        <div className="li-sub" style={{ marginTop: 6 }}>
                          {ef
                            ? efMonths != null
                              ? `${money(efContribution, plan.currency)}/mo → fills ${money(ef.gap, plan.currency)} gap in ~${efMonths} ${efMonths === 1 ? "month" : "months"} (${money(ef.current_amount, plan.currency)} / ${money(ef.target, plan.currency)})`
                              : `${money(ef.current_amount, plan.currency)} / ${money(ef.target, plan.currency)} saved — set how much to put aside`
                            : "Set how much to put aside each month."}
                        </div>
                      </div>
                    )}
                  </li>
                )}

                {/* Everything else splits what's left after debt + emergency fund */}
                {otherBuckets.map((b, i) => (
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
                        {money(bucketAmt(b), plan.currency)}
                      </strong>
                      <button className="btn btn--ghost" style={{ padding: "0 6px" }}
                        onClick={() => remove(b.id)} title="Remove">×</button>
                    </span>
                  </li>
                ))}

                {otherBuckets.length === 0 && !debtBucket && !efBucket ? (
                  <li className="muted" style={{ justifyContent: "center" }}>
                    Add buckets to split {money(distributable, plan.currency)}.
                  </li>
                ) : over ? (
                  <li>
                    <span className="li-main neg">⚠ Over 100% — reduce a bucket</span>
                    <span className="neg">{allocatedPct}%</span>
                  </li>
                ) : unallocPct > 0 && otherBuckets.length > 0 ? (
                  <li style={{ opacity: 0.75 }}>
                    <span className="li-main muted">Unallocated · {unallocPct}%</span>
                    <span className="muted">{money((unallocPct / 100) * distributable, plan.currency)}</span>
                  </li>
                ) : null}
              </ul>

              {unpaidDebts.length > 0 && !debtBucket && (
                <button className="btn btn--ghost btn--sm" style={{ marginTop: 10, marginRight: 8 }}
                  onClick={addDebtBucket} disabled={busy}>
                  🎯 Pay off debt? ({money(outstanding, plan.currency)} owed)
                </button>
              )}
              {ef && efGap > 0 && !efBucket && (
                <button className="btn btn--ghost btn--sm" style={{ marginTop: 10 }}
                  onClick={addEfBucket} disabled={busy}>
                  💰 Fill emergency fund? ({money(ef.gap, plan.currency)} to go)
                </button>
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
