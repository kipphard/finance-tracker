import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiDelete, apiPatch, apiPost } from "../api/client";
import type {
  AccountOut,
  DebtOut,
  EmergencyFundOut,
  OneoffAllocationOut,
  PlannedPurchasesOut,
  TaxReserveOut,
} from "../api/types";
import { money, num } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";
import { Modal } from "./Modal";

const COLORS = ["#6366f1", "#10b981", "#f59e0b", "#06b6d4", "#a855f7", "#ec4899", "#84cc16"];
const EF_COLOR = "#14b8a6";
const PP_COLOR = "#f97316";
const TAX_COLOR = "#eab308";
const DEBT_COLOR = "#ef4444";

const round2 = (n: number) => Math.round(n * 100) / 100;

// One-off "Distribute a windfall" card. A near-copy of AllocationCard, but with its OWN persistent
// set of buckets (/oneoff-allocations) so it never shows or touches the monthly distribution, and
// the amount being split is whatever the user types (a bonus/gift/refund) instead of the computed
// monthly leftover. Debt / emergency fund / Steuerrücklage / planned purchases are taken off the
// top (all optional), then the % buckets split the remainder. Applying books real transfers
// immediately via /allocations/distribute-oneoff (no month guard, no monthly apply-log).
export function OneoffDistributeCard({ className }: { className?: string }) {
  const bucketsApi = useApi<OneoffAllocationOut[]>("/oneoff-allocations");
  const accountsApi = useApi<AccountOut[]>("/accounts");
  const debtsApi = useApi<DebtOut[]>("/debts");
  const efApi = useApi<EmergencyFundOut>("/emergency-fund");
  const ppApi = useApi<PlannedPurchasesOut>("/planned-purchases");
  const trApi = useApi<TaxReserveOut>("/tax-reserve");

  const [amount, setAmount] = useState("");
  const [source, setSource] = useState("");
  const [pctDraft, setPctDraft] = useState<Record<string, string>>({}); // per-bucket % being edited
  const [debtTicked, setDebtTicked] = useState<Record<string, boolean>>({});
  const [payDraft, setPayDraft] = useState<Record<string, string>>({}); // per-debt € override
  const [efPut, setEfPut] = useState("");
  const [taxPut, setTaxPut] = useState("");
  const [plannedPut, setPlannedPut] = useState<Record<string, string>>({});
  const [name, setName] = useState("");
  const [percent, setPercent] = useState("");
  const [applyOpen, setApplyOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [addBusy, setAddBusy] = useState(false);

  const clearPct = (id: string) =>
    setPctDraft((d) => {
      const next = { ...d };
      delete next[id];
      return next;
    });

  const addBucket = async () => {
    if (!name.trim() || !percent) return;
    setAddBusy(true);
    try {
      await apiPost("/oneoff-allocations", { name: name.trim(), percent });
      setName("");
      setPercent("");
      bucketsApi.reload();
    } finally {
      setAddBusy(false);
    }
  };

  const commitPercent = async (id: string, current: string) => {
    const v = pctDraft[id];
    if (v == null || v === "" || num(v) === num(current)) {
      clearPct(id);
      return;
    }
    await apiPatch(`/oneoff-allocations/${id}`, { percent: v });
    clearPct(id);
    bucketsApi.reload();
  };

  const linkBucket = async (id: string, accountId: string) => {
    await apiPatch(`/oneoff-allocations/${id}`, { account_id: accountId || null });
    bucketsApi.reload();
  };

  const removeBucket = async (id: string) => {
    await apiDelete(`/oneoff-allocations/${id}`);
    bucketsApi.reload();
  };

  return (
    <Card title="Distribute a one-off amount" className={className}>
      <Async state={bucketsApi}>
        {(buckets) => {
          const entered = num(amount);
          const accounts = accountsApi.data ?? [];
          const accById = new Map(accounts.map((a) => [a.id, a.name]));
          const src = source || (accounts[0]?.id ?? "");
          const currency =
            accounts.find((a) => a.id === src)?.currency ?? accounts[0]?.currency ?? "EUR";
          const colorOf = new Map(buckets.map((b, i) => [b.id, COLORS[i % COLORS.length]]));

          const unpaidDebts = (debtsApi.data ?? []).filter((d) => !d.paid);
          const ef = efApi.data;
          const tr = trApi.data;
          const plannedItems = (ppApi.data?.items ?? []).filter((it) => it.account_id);

          // --- off the top: debt → emergency fund → Steuerrücklage → planned purchases ---
          const payOf = (d: DebtOut) => payDraft[d.id] ?? String(num(d.amount)); // default = full owed
          const debtMoves = unpaidDebts
            .filter((d) => debtTicked[d.id] && num(payOf(d)) > 0)
            .map((d) => ({ debt_id: d.id, amount: num(payOf(d)), name: d.name }));
          const debtPay = debtMoves.reduce((s, m) => s + m.amount, 0);

          const efCanReceive = !!ef?.account_id;
          const taxCanReceive = !!tr?.reserve_account_id;
          const efAmt = efCanReceive ? num(efPut) : 0;
          const taxAmt = taxCanReceive ? num(taxPut) : 0;
          const plannedMoves = plannedItems
            .filter((it) => num(plannedPut[it.id] ?? "") > 0)
            .map((it) => ({
              to: it.account_id as string,
              amount: num(plannedPut[it.id]),
              label: `Planned: ${it.name}`,
            }));
          const plannedTotal = plannedMoves.reduce((s, m) => s + m.amount, 0);

          const offTop = debtPay + efAmt + taxAmt + plannedTotal;
          const distributable = Math.max(0, entered - offTop);

          const allocatedPct = buckets.reduce((s, b) => s + num(b.percent), 0);
          const over100 = allocatedPct > 100;
          const denomPct = Math.max(100, allocatedPct);
          const unallocPct = Math.max(0, 100 - allocatedPct);
          const bucketAmt = (b: OneoffAllocationOut) => (num(b.percent) / 100) * distributable;

          // --- map every funded destination to a real transfer (buckets that have a linked
          //     account, plus the off-the-top targets) ---
          const transferMoves = [
            ...(efAmt > 0 && ef?.account_id
              ? [{ to: ef.account_id, amount: efAmt, label: "Emergency fund", account: accById.get(ef.account_id) ?? "?", color: EF_COLOR }]
              : []),
            ...(taxAmt > 0 && tr?.reserve_account_id
              ? [{ to: tr.reserve_account_id, amount: taxAmt, label: "Steuerrücklage", account: accById.get(tr.reserve_account_id) ?? "?", color: TAX_COLOR }]
              : []),
            ...plannedMoves.map((m) => ({ to: m.to, amount: m.amount, label: m.label, account: accById.get(m.to) ?? "?", color: PP_COLOR })),
            ...buckets
              .filter((b) => b.account_id && bucketAmt(b) > 0)
              .map((b) => ({ to: b.account_id as string, amount: bucketAmt(b), label: b.name, account: accById.get(b.account_id as string) ?? "?", color: colorOf.get(b.id) as string })),
          ];

          const allocated = transferMoves.reduce((s, m) => s + m.amount, 0) + debtPay;
          const leftover = round2(entered - allocated);
          const canApply = entered > 0 && !!src && (transferMoves.length > 0 || debtMoves.length > 0);

          // Stacked allocation bar — one segment per money move + grey "stays in source" remainder.
          const segments = [
            ...transferMoves.map((m) => ({ amount: m.amount, color: m.color })),
            ...(debtPay > 0 ? [{ amount: debtPay, color: DEBT_COLOR }] : []),
          ];
          const denom = Math.max(entered, allocated) || 1;
          const restPct = leftover > 0 ? (leftover / denom) * 100 : 0;

          const doApply = async () => {
            if (!canApply) return;
            setBusy(true);
            try {
              await apiPost("/allocations/distribute-oneoff", {
                source_account_id: src,
                amount,
                transfers: transferMoves.map((m) => ({ to_account_id: m.to, amount: String(m.amount), label: m.label })),
                debt_payments: debtMoves.map((m) => ({ debt_id: m.debt_id, amount: String(m.amount) })),
              });
              setApplyOpen(false);
              // reset the windfall-specific inputs, but keep the saved buckets
              setAmount("");
              setDebtTicked({});
              setPayDraft({});
              setEfPut("");
              setTaxPut("");
              setPlannedPut({});
              accountsApi.reload();
              debtsApi.reload();
              efApi.reload();
              trApi.reload();
              ppApi.reload();
            } finally {
              setBusy(false);
            }
          };

          return (
            <>
              <div className="muted" style={{ fontSize: 12 }}>
                Got a bonus, gift, refund or any one-off windfall? Drop the amount in and split it
                across your own buckets right now — separate from the monthly distribution, no
                waiting for month-end.
              </div>

              <div className="toolbar" style={{ marginTop: 10 }}>
                <input
                  className="input"
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="Amount (e.g. 1000)"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  style={{ flex: 1 }}
                />
                <select className="select" value={src} onChange={(e) => setSource(e.target.value)}
                  title="Account the windfall landed in / pays out from">
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>from {a.name}</option>
                  ))}
                </select>
              </div>

              <div className="alloc__leftover" style={{ marginTop: 10 }}>
                {money(distributable, currency)}{" "}
                <span className="muted" style={{ fontSize: 12, fontWeight: 400 }}>to distribute</span>
              </div>

              {segments.length > 0 && (
                <div className="alloc__bar">
                  {segments.map((s, i) => (
                    <div key={i} className="alloc__seg"
                      style={{ width: `${(s.amount / denom) * 100}%`, background: s.color }} />
                  ))}
                  {restPct > 0 && (
                    <div className="alloc__seg alloc__seg--rest" style={{ width: `${restPct}%` }} />
                  )}
                </div>
              )}

              <ul className="list">
                {/* Debt — grouped, off the top: tick which debts to pay down with the windfall */}
                {unpaidDebts.length > 0 && (
                  <li style={{ display: "block" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span className="li-main">
                        <span className="alloc__dot" style={{ background: DEBT_COLOR }} />
                        🎯 Pay off debt <span className="muted" style={{ fontWeight: 400 }}>· off the top</span>
                      </span>
                      <strong style={{ minWidth: 78, textAlign: "right" }}>{money(debtPay, currency)}</strong>
                    </div>
                    <div className="alloc__debt">
                      <div className="alloc__debtlist">
                        {unpaidDebts.map((d) => {
                          const checked = !!debtTicked[d.id];
                          return (
                            <div key={d.id} className="alloc__tick">
                              <input type="checkbox" checked={checked}
                                onChange={(e) => setDebtTicked((m) => ({ ...m, [d.id]: e.target.checked }))} />
                              <span>{d.name} <span className="muted">· {money(d.amount, currency)}</span></span>
                              {checked && (
                                <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
                                  <span className="muted" style={{ fontSize: 11 }}>pay</span>
                                  <input className="input alloc__amt" type="number" min="0" step="0.01"
                                    value={payOf(d)}
                                    onChange={(e) => setPayDraft((m) => ({ ...m, [d.id]: e.target.value }))} />
                                  <span className="muted">€</span>
                                </span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                      <div className="li-sub" style={{ marginTop: 6 }}>
                        {debtMoves.length > 0
                          ? `Paying ${money(debtPay, currency)} across ${debtMoves.length} ${debtMoves.length === 1 ? "debt" : "debts"} with this windfall`
                          : "Tick a debt to pay it down with this windfall."}
                      </div>
                    </div>
                  </li>
                )}

                {/* Emergency fund — off the top (optional) */}
                {ef && (
                  <li>
                    <span className="li-main">
                      <span className="alloc__dot" style={{ background: EF_COLOR }} />
                      💰 Emergency fund
                      {!efCanReceive && (
                        <span className="muted" style={{ fontWeight: 400 }}> · link an account in the Emergency fund card</span>
                      )}
                    </span>
                    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      {efCanReceive && ef.account_id && (
                        <span className="muted" style={{ fontSize: 12 }}>→ {accById.get(ef.account_id)}</span>
                      )}
                      <input className="input alloc__amt" type="number" min="0" step="0.01" placeholder="0"
                        disabled={!efCanReceive}
                        value={efPut}
                        onChange={(e) => setEfPut(e.target.value)} />
                      <span className="muted">€</span>
                    </span>
                  </li>
                )}

                {/* Steuerrücklage — off the top (optional) */}
                {tr && (
                  <li>
                    <span className="li-main">
                      <span className="alloc__dot" style={{ background: TAX_COLOR }} />
                      🧾 Steuerrücklage
                      {!taxCanReceive && (
                        <span className="muted" style={{ fontWeight: 400 }}> · link a reserve account in the Steuerrücklage card</span>
                      )}
                    </span>
                    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      {taxCanReceive && tr.reserve_account_id && (
                        <span className="muted" style={{ fontSize: 12 }}>→ {accById.get(tr.reserve_account_id)}</span>
                      )}
                      <input className="input alloc__amt" type="number" min="0" step="0.01" placeholder="0"
                        disabled={!taxCanReceive}
                        value={taxPut}
                        onChange={(e) => setTaxPut(e.target.value)} />
                      <span className="muted">€</span>
                    </span>
                  </li>
                )}

                {/* Planned purchases — off the top, only items with a linked account (optional) */}
                {plannedItems.map((it) => (
                  <li key={`pp:${it.id}`}>
                    <span className="li-main">
                      <span className="alloc__dot" style={{ background: PP_COLOR }} />
                      🛍️ {it.name}
                    </span>
                    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span className="muted" style={{ fontSize: 12 }}>→ {accById.get(it.account_id as string)}</span>
                      <input className="input alloc__amt" type="number" min="0" step="0.01" placeholder="0"
                        value={plannedPut[it.id] ?? ""}
                        onChange={(e) => setPlannedPut((m) => ({ ...m, [it.id]: e.target.value }))} />
                      <span className="muted">€</span>
                    </span>
                  </li>
                ))}

                {/* The user's own % buckets split whatever is left */}
                {buckets.map((b) => (
                  <li key={b.id}>
                    <span className="li-main">
                      <span className="alloc__dot" style={{ background: colorOf.get(b.id) }} />
                      {b.name}
                    </span>
                    <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <select className="select" style={{ maxWidth: 130, fontSize: 12 }}
                        value={b.account_id ?? ""}
                        onChange={(e) => linkBucket(b.id, e.target.value)}
                        title="Destination account for 'Distribute now'">
                        <option value="">no account</option>
                        {accounts.map((a) => (
                          <option key={a.id} value={a.id}>→ {a.name}</option>
                        ))}
                      </select>
                      <input
                        className="input alloc__pct"
                        type="number"
                        min="0"
                        max="100"
                        step="0.5"
                        value={pctDraft[b.id] ?? String(num(b.percent))}
                        onChange={(e) => setPctDraft((d) => ({ ...d, [b.id]: e.target.value }))}
                        onBlur={() => commitPercent(b.id, b.percent)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                        }}
                      />
                      <span className="muted">%</span>
                      <strong style={{ minWidth: 78, textAlign: "right" }}>
                        {money(bucketAmt(b), currency)}
                      </strong>
                      <button className="btn btn--ghost" style={{ padding: "0 6px" }}
                        onClick={() => removeBucket(b.id)} title="Remove">×</button>
                    </span>
                  </li>
                ))}

                {buckets.length === 0 ? (
                  <li className="muted" style={{ justifyContent: "center" }}>
                    Add your own buckets below to split the windfall.
                  </li>
                ) : over100 ? (
                  <li>
                    <span className="li-main neg">⚠ Over 100% — reduce a bucket</span>
                    <span className="neg">{allocatedPct}%</span>
                  </li>
                ) : leftover < 0 ? (
                  <li>
                    <span className="li-main neg">⚠ Over-allocated — moving more than the windfall</span>
                    <span className="neg">{money(-leftover, currency)}</span>
                  </li>
                ) : leftover > 0 ? (
                  <li style={{ opacity: 0.75 }}>
                    <span className="li-main muted">
                      Stays in source{unallocPct > 0 && buckets.length > 0 ? ` · ${unallocPct}% unallocated` : ""}
                    </span>
                    <span className="muted">{money(leftover, currency)}</span>
                  </li>
                ) : null}
              </ul>

              {canApply && (
                <div style={{ marginTop: 12 }}>
                  <button className="btn btn--sm" onClick={() => setApplyOpen(true)} disabled={busy}>
                    ✅ Distribute now → {money(allocated, currency)}
                  </button>
                </div>
              )}

              <div className="toolbar" style={{ marginTop: 12 }}>
                <input className="input" placeholder="Bucket (e.g. Extra sparen)" value={name}
                  onChange={(e) => setName(e.target.value)} />
                <input className="input" type="number" min="0" max="100" step="0.5" placeholder="%"
                  value={percent} onChange={(e) => setPercent(e.target.value)} style={{ width: 80 }} />
                <button className="btn" onClick={addBucket} disabled={addBusy || !name.trim() || !percent}>Add</button>
              </div>

              {applyOpen && (
                <Modal title="Distribute this one-off amount" onClose={() => setApplyOpen(false)}>
                  <div className="form">
                    <div className="field">
                      <label>From account (source)</label>
                      <select className="select" value={src} onChange={(e) => setSource(e.target.value)}>
                        {accounts.map((a) => (
                          <option key={a.id} value={a.id}>{a.name}</option>
                        ))}
                      </select>
                    </div>
                    <ul className="list">
                      {transferMoves.map((m, i) => (
                        <li key={"t" + i}>
                          <span className="li-main">→ {m.label}</span>
                          <span>{money(m.amount, currency)}{" "}
                            <span className="muted">to {m.account}</span></span>
                        </li>
                      ))}
                      {debtMoves.map((m, i) => (
                        <li key={"d" + i}>
                          <span className="li-main">→ Pay {m.name}</span>
                          <span>{money(m.amount, currency)}{" "}
                            <span className="muted">from source</span></span>
                        </li>
                      ))}
                    </ul>
                    <div className="muted" style={{ fontSize: 12 }}>
                      Books real transfers between your accounts and debt payments as expenses
                      (cleared debts are marked paid). Total moved:{" "}
                      <strong>{money(allocated, currency)}</strong>
                      {leftover > 0 ? (
                        <> · {money(leftover, currency)} stays in source.</>
                      ) : leftover < 0 ? (
                        <span className="neg"> · {money(-leftover, currency)} over the windfall.</span>
                      ) : (
                        "."
                      )}
                    </div>
                    <div className="form__actions">
                      <button type="button" className="btn btn--ghost"
                        onClick={() => setApplyOpen(false)}>Cancel</button>
                      <button type="button" className="btn" onClick={doApply}
                        disabled={busy || !canApply}>{busy ? "…" : "Distribute"}</button>
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
