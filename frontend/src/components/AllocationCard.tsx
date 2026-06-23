import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiDelete, apiPatch, apiPost } from "../api/client";
import type { AccountOut, AllocationPlanOut, DebtOut, EmergencyFundOut, PlannedPurchasesOut, TaxReserveOut } from "../api/types";
import { money, num } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";
import { Modal } from "./Modal";

const COLORS = ["#6366f1", "#10b981", "#f59e0b", "#06b6d4", "#a855f7", "#ec4899", "#84cc16"];
const DEBT_COLOR = "#ef4444";
const EF_COLOR = "#14b8a6";
const PP_COLOR = "#f97316";
const TAX_COLOR = "#eab308";
const TICK_KEY = "ft_debt_payoff_ids";
const PAY_KEY = "ft_debt_pay_amounts";
const EF_KEY = "ft_ef_contribution";
const EF_MODE_KEY = "ft_ef_mode";

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
  const ppApi = useApi<PlannedPurchasesOut>("/planned-purchases");
  const trApi = useApi<TaxReserveOut>("/tax-reserve");
  const accountsApi = useApi<AccountOut[]>("/accounts");
  const [applyOpen, setApplyOpen] = useState(false);
  const [applySource, setApplySource] = useState("");
  const [applyBusy, setApplyBusy] = useState(false);
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
  const [efMode, setEfModeRaw] = useState<"amount" | "percent">(() => {
    try {
      return localStorage.getItem(EF_MODE_KEY) === "percent" ? "percent" : "amount";
    } catch {
      return "amount";
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
  const setEfMode = (m: "amount" | "percent") => {
    setEfModeRaw(m);
    saveEfPay(""); // value means something different per mode; start fresh
    try {
      localStorage.setItem(EF_MODE_KEY, m);
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

  const linkBucket = async (id: string, accountId: string) => {
    await apiPatch(`/allocations/${id}`, { account_id: accountId || null });
    state.reload();
  };

  const earmarkBucket = async (id: string, earmarked: boolean) => {
    await apiPatch(`/allocations/${id}`, { earmarked });
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

          // Debts are the first claim; the emergency-fund cut comes out of what's left after debt.
          const afterDebt = Math.max(0, gross - debtPay);

          const ef = efApi.data;
          // Contribution is a fixed € or a % of the leftover remaining after debt.
          const efContribution = efBucket
            ? efMode === "percent"
              ? (num(efPay) / 100) * afterDebt
              : Math.min(num(efPay), afterDebt)
            : 0;
          const efGap = ef ? num(ef.gap) : 0;
          const efMonths = efContribution > 0 && efGap > 0 ? Math.ceil(efGap / efContribution) : null;

          const plannedFund = num(ppApi.data?.planned_fund ?? 0);
          const plannedCount = ppApi.data?.items.length ?? 0;
          // Tax reserve (Steuerrücklage) — the recommended monthly set-aside, also off the top.
          const taxReserve = num(trApi.data?.recommended_monthly ?? 0);
          // Then planned purchases, Steuerrücklage, and the percentage buckets share the rest.
          const distributable = Math.max(0, afterDebt - efContribution - plannedFund - taxReserve);
          const allocatedPct = otherBuckets.reduce((s, b) => s + num(b.percent), 0);
          const over = allocatedPct > 100;
          const denom = Math.max(100, allocatedPct);
          const unallocPct = Math.max(0, 100 - allocatedPct);
          const bucketAmt = (b: { percent: string }) => (num(b.percent) / 100) * distributable;

          // --- "Apply this month": map linked buckets + ticked debts to real money moves ---
          const accById = new Map((accountsApi.data ?? []).map((a) => [a.id, a.name]));
          const efAccount = efBucket && ef?.account_id ? ef.account_id : null;
          const transferMoves: { to: string; amount: number; label: string; account: string }[] = [
            ...(efAccount && efContribution > 0
              ? [{ to: efAccount, amount: efContribution, label: "Emergency fund", account: accById.get(efAccount) ?? "?" }]
              : []),
            ...otherBuckets
              .filter((b) => b.account_id && bucketAmt(b) > 0)
              .map((b) => ({ to: b.account_id as string, amount: bucketAmt(b), label: b.name, account: accById.get(b.account_id as string) ?? "?" })),
            ...(ppApi.data?.items ?? [])
              .filter((it) => it.account_id && num(it.monthly_save) > 0)
              .map((it) => ({ to: it.account_id as string, amount: num(it.monthly_save), label: `Planned: ${it.name}`, account: accById.get(it.account_id as string) ?? "?" })),
          ];
          const debtMoves = debtBucket
            ? unpaidDebts
                .filter((d) => tickedSet.has(d.id) && num(amountFor(d)) > 0)
                .map((d) => ({ debt_id: d.id, amount: num(amountFor(d)), name: d.name }))
            : [];
          const applyTotal = transferMoves.reduce((s, m) => s + m.amount, 0)
            + debtMoves.reduce((s, m) => s + m.amount, 0);
          const canApply = transferMoves.length > 0 || debtMoves.length > 0;
          const source = applySource || (accountsApi.data?.[0]?.id ?? "");
          // Guard against booking the same month twice.
          const lastApplied = plan.last_applied_at ? new Date(plan.last_applied_at) : null;
          const nowD = new Date();
          const appliedThisMonth = !!lastApplied
            && lastApplied.getFullYear() === nowD.getFullYear()
            && lastApplied.getMonth() === nowD.getMonth();
          const doApply = async () => {
            if (!source) return;
            setApplyBusy(true);
            try {
              await apiPost("/allocations/apply", {
                source_account_id: source,
                transfers: transferMoves.map((m) => ({ to_account_id: m.to, amount: String(m.amount), label: m.label })),
                debt_payments: debtMoves.map((m) => ({ debt_id: m.debt_id, amount: String(m.amount) })),
              });
              setApplyOpen(false);
              debtsApi.reload();
              efApi.reload();
              state.reload();
            } finally {
              setApplyBusy(false);
            }
          };

          return (
            <>
              <div className="muted" style={{ fontSize: 12 }}>
                {money(plan.monthly_income, plan.currency)} income −{" "}
                {money(plan.monthly_fixed, plan.currency)} fixed costs
                {debtPay > 0 ? ` − ${money(debtPay, plan.currency)} debt` : ""}
                {efContribution > 0 ? ` − ${money(efContribution, plan.currency)} emergency fund` : ""}
                {plannedFund > 0 ? ` − ${money(plannedFund, plan.currency)} planned purchases` : ""}
                {taxReserve > 0 ? ` − ${money(taxReserve, plan.currency)} Steuerrücklage` : ""}
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
                          <span className="muted" style={{ fontSize: 11 }}>
                            put / month{efMode === "percent" && efContribution > 0 ? ` · ${money(efContribution, plan.currency)}` : ""}
                          </span>
                          <input
                            className="input alloc__amt"
                            style={{ marginLeft: "auto" }}
                            type="number"
                            min="0"
                            step={efMode === "percent" ? "0.5" : "0.01"}
                            value={efPay}
                            onChange={(e) => saveEfPay(e.target.value)}
                          />
                          <button type="button" className="btn btn--ghost btn--sm"
                            style={{ padding: "2px 8px" }}
                            onClick={() => setEfMode(efMode === "percent" ? "amount" : "percent")}
                            title="Switch between € and % of leftover after debt">
                            {efMode === "percent" ? "%" : "€"}
                          </button>
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

                {/* Planned purchases fund — sum of per-item monthly saves, also off the top */}
                {plannedFund > 0 && (
                  <li style={{ display: "block" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span className="li-main">
                        <span className="alloc__dot" style={{ background: PP_COLOR }} />
                        🛍️ Planned purchases{" "}
                        <span className="muted" style={{ fontWeight: 400 }}>· off the top</span>
                      </span>
                      <strong style={{ minWidth: 78, textAlign: "right" }}>
                        {money(plannedFund, plan.currency)}
                      </strong>
                    </div>
                    <div className="li-sub" style={{ marginTop: 6 }}>
                      Saving for {plannedCount} {plannedCount === 1 ? "item" : "items"} — set amounts in
                      the <b>Planned purchases</b> card.
                    </div>
                  </li>
                )}

                {/* Tax reserve — the §32a-derived monthly set-aside, also off the top */}
                {taxReserve > 0 && (
                  <li style={{ display: "block" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span className="li-main">
                        <span className="alloc__dot" style={{ background: TAX_COLOR }} />
                        🧾 Steuerrücklage{" "}
                        <span className="muted" style={{ fontWeight: 400 }}>· off the top</span>
                      </span>
                      <strong style={{ minWidth: 78, textAlign: "right" }}>
                        {money(taxReserve, plan.currency)}
                      </strong>
                    </div>
                    <div className="li-sub" style={{ marginTop: 6 }}>
                      {trApi.data
                        ? `${money(trApi.data.gap, plan.currency)} noch offen für ${trApi.data.year} — passt sich im Steuerrücklage-Card an.`
                        : "Recommended income-tax set-aside — adjust in the Steuerrücklage card."}
                    </div>
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
                      <select className="select" style={{ maxWidth: 130, fontSize: 12 }}
                        value={b.account_id ?? ""}
                        onChange={(e) => linkBucket(b.id, e.target.value)}
                        title="Destination account for 'Apply this month'">
                        <option value="">no account</option>
                        {(accountsApi.data ?? []).map((a) => (
                          <option key={a.id} value={a.id}>→ {a.name}</option>
                        ))}
                      </select>
                      {b.account_id && (
                        <label className="muted" style={{ display: "flex", alignItems: "center", gap: 2, fontSize: 11 }}
                          title="Exclude this account from cash runway">
                          <input type="checkbox" checked={b.earmarked}
                            onChange={(e) => earmarkBucket(b.id, e.target.checked)} />
                          🔒
                        </label>
                      )}
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

              {canApply && (
                <div style={{ marginTop: 12 }}>
                  <button className="btn btn--sm"
                    onClick={() => setApplyOpen(true)} disabled={busy}>
                    ✅ Apply this month → {money(applyTotal, plan.currency)}
                  </button>
                  {lastApplied && (
                    <span className="muted" style={{ fontSize: 11, marginLeft: 8 }}>
                      {appliedThisMonth ? "✓ already applied " : "last applied "}
                      {lastApplied.toLocaleDateString()}
                    </span>
                  )}
                </div>
              )}

              <div className="toolbar" style={{ marginTop: 12 }}>
                <input className="input" placeholder="Bucket (e.g. Savings)" value={name}
                  onChange={(e) => setName(e.target.value)} />
                <input className="input" type="number" min="0" max="100" step="0.5" placeholder="%"
                  value={percent} onChange={(e) => setPercent(e.target.value)} style={{ width: 80 }} />
                <button className="btn" onClick={add} disabled={busy || !name.trim() || !percent}>Add</button>
              </div>

              {applyOpen && (
                <Modal title="Apply this month's distribution" onClose={() => setApplyOpen(false)}>
                  <div className="form">
                    {appliedThisMonth && (
                      <div className="error" style={{ background: "rgba(245,158,11,0.12)", color: "var(--warning, #b45309)" }}>
                        ⚠ Already applied this month (on {lastApplied!.toLocaleDateString()}). Applying
                        again will book <b>duplicate</b> transfers and debt payments.
                      </div>
                    )}
                    <div className="field">
                      <label>From account (source)</label>
                      <select className="select" value={source}
                        onChange={(e) => setApplySource(e.target.value)}>
                        {(accountsApi.data ?? []).map((a) => (
                          <option key={a.id} value={a.id}>{a.name}</option>
                        ))}
                      </select>
                    </div>
                    <ul className="list">
                      {transferMoves.map((m, i) => (
                        <li key={"t" + i}>
                          <span className="li-main">→ {m.label}</span>
                          <span>{money(m.amount, plan.currency)}{" "}
                            <span className="muted">to {m.account}</span></span>
                        </li>
                      ))}
                      {debtMoves.map((m, i) => (
                        <li key={"d" + i}>
                          <span className="li-main">→ Pay {m.name}</span>
                          <span>{money(m.amount, plan.currency)}{" "}
                            <span className="muted">from source</span></span>
                        </li>
                      ))}
                    </ul>
                    <div className="muted" style={{ fontSize: 12 }}>
                      Books real transfers between your accounts and debt payments as expenses
                      (cleared debts are marked paid). Total moved:{" "}
                      <strong>{money(applyTotal, plan.currency)}</strong>.
                    </div>
                    <div className="form__actions">
                      <button type="button" className="btn btn--ghost"
                        onClick={() => setApplyOpen(false)}>Cancel</button>
                      <button type="button" className="btn" onClick={doApply}
                        disabled={applyBusy || !source}>{applyBusy ? "…" : "Apply"}</button>
                    </div>
                  </div>
                </Modal>
              )}
            </>
          );
        }}
      </Async>
    </Card>
  );
}
