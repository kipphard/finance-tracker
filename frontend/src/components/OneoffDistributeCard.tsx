import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiPost } from "../api/client";
import type {
  AccountOut,
  AllocationPlanOut,
  DebtOut,
  EmergencyFundOut,
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

const isDebtBucket = (name: string) => name.trim().toLowerCase() === "debt";
const isEfBucket = (name: string) => name.trim().toLowerCase() === "emergency fund";
const round2 = (n: number) => Math.round(n * 100) / 100;

// A one-off windfall (bonus, gift, refund) split across the same buckets/targets as the monthly
// distribution, but applied immediately. Mirrors AllocationCard's layout (allocation bar, grouped
// Debt box, per-bucket rows) so the two distribution cards feel like one family. It reuses the saved
// bucket percentages as a starting point and books real transfers right away — see the backend
// /allocations/distribute-oneoff endpoint, which deliberately does NOT touch the monthly "already
// applied this month" marker.
export function OneoffDistributeCard({ className }: { className?: string }) {
  const planApi = useApi<AllocationPlanOut>("/allocations/plan");
  const accountsApi = useApi<AccountOut[]>("/accounts");
  const debtsApi = useApi<DebtOut[]>("/debts");
  const efApi = useApi<EmergencyFundOut>("/emergency-fund");
  const ppApi = useApi<PlannedPurchasesOut>("/planned-purchases");
  const trApi = useApi<TaxReserveOut>("/tax-reserve");

  const [amount, setAmount] = useState("");
  const [source, setSource] = useState("");
  const [amounts, setAmounts] = useState<Record<string, string>>({}); // per-destination € overrides
  const [debtTicked, setDebtTicked] = useState<Record<string, boolean>>({}); // which debts to pay
  const [payDraft, setPayDraft] = useState<Record<string, string>>({}); // per-debt € override
  const [applyOpen, setApplyOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  return (
    <Card title="Distribute a one-off amount" className={className}>
      <Async state={planApi}>
        {(plan) => {
          const currency = plan.currency;
          const entered = num(amount);
          const accounts = accountsApi.data ?? [];
          const accById = new Map(accounts.map((a) => [a.id, a.name]));
          const src = source || (accounts[0]?.id ?? "");

          // Real percentage buckets — skip the Debt / Emergency-fund pseudo-buckets, which have
          // their own destinations below.
          const pctBuckets = plan.buckets.filter(
            (b) => !isDebtBucket(b.name) && !isEfBucket(b.name),
          );
          const ef = efApi.data;
          const tr = trApi.data;
          const plannedItems = (ppApi.data?.items ?? []).filter((it) => it.account_id);
          const unpaidDebts = (debtsApi.data ?? []).filter((d) => !d.paid);

          // Transfer destinations rendered as bucket rows. Buckets pre-fill from their saved %; the
          // special targets default to 0 (opt-in for this particular windfall). A bucket with no
          // linked account can't receive money — shown disabled with a hint. EF / Steuerrücklage /
          // planned items only appear once they have a linked account.
          type Row = {
            key: string;
            label: string;
            accountId: string | null;
            def: number;
            color: string;
            hint?: string;
          };
          const rows: Row[] = [
            ...pctBuckets.map((b, i) => ({
              key: `b:${b.id}`,
              label: b.name,
              accountId: b.account_id,
              def: round2((num(b.percent) / 100) * entered),
              color: COLORS[i % COLORS.length],
              hint: b.account_id ? undefined : "link an account in 'Distribute leftover'",
            })),
            ...(ef && ef.account_id
              ? [{ key: "ef", label: "Emergency fund", accountId: ef.account_id, def: 0, color: EF_COLOR }]
              : []),
            ...(tr && tr.reserve_account_id
              ? [{ key: "tax", label: "Steuerrücklage", accountId: tr.reserve_account_id, def: 0, color: TAX_COLOR }]
              : []),
            ...plannedItems.map((it) => ({
              key: `pp:${it.id}`,
              label: `Planned: ${it.name}`,
              accountId: it.account_id,
              def: 0,
              color: PP_COLOR,
            })),
          ];

          const valFor = (r: Row) => num(amounts[r.key] ?? String(r.def));
          const payOf = (d: DebtOut) => payDraft[d.id] ?? String(num(d.amount)); // default = full owed

          const transferMoves = rows
            .filter((r) => r.accountId && valFor(r) > 0)
            .map((r) => ({
              to: r.accountId as string,
              amount: valFor(r),
              label: r.label,
              account: accById.get(r.accountId as string) ?? "?",
              color: r.color,
            }));
          const debtMoves = unpaidDebts
            .filter((d) => debtTicked[d.id] && num(payOf(d)) > 0)
            .map((d) => ({ debt_id: d.id, amount: num(payOf(d)), name: d.name }));
          const debtPayTotal = debtMoves.reduce((s, m) => s + m.amount, 0);

          const allocated = transferMoves.reduce((s, m) => s + m.amount, 0) + debtPayTotal;
          const leftover = round2(entered - allocated);
          const canApply = entered > 0 && !!src && (transferMoves.length > 0 || debtMoves.length > 0);

          // Stacked allocation bar — one segment per money move, plus a grey "stays in source" rest.
          const segments = [
            ...transferMoves.map((m) => ({ amount: m.amount, color: m.color })),
            ...(debtPayTotal > 0 ? [{ amount: debtPayTotal, color: DEBT_COLOR }] : []),
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
                transfers: transferMoves.map((m) => ({
                  to_account_id: m.to,
                  amount: String(m.amount),
                  label: m.label,
                })),
                debt_payments: debtMoves.map((m) => ({ debt_id: m.debt_id, amount: String(m.amount) })),
              });
              setApplyOpen(false);
              setAmount("");
              setAmounts({});
              setDebtTicked({});
              setPayDraft({});
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
                across your buckets right now — separate from the monthly distribution, no waiting
                for month-end.
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

              {entered > 0 ? (
                <>
                  <div className="alloc__leftover" style={{ marginTop: 10 }}>
                    {money(entered, currency)}{" "}
                    <span className="muted" style={{ fontSize: 12, fontWeight: 400 }}>to distribute</span>
                  </div>

                  {segments.length > 0 && (
                    <div className="alloc__bar">
                      {segments.map((s, i) => (
                        <div
                          key={i}
                          className="alloc__seg"
                          style={{ width: `${(s.amount / denom) * 100}%`, background: s.color }}
                        />
                      ))}
                      {restPct > 0 && (
                        <div className="alloc__seg alloc__seg--rest" style={{ width: `${restPct}%` }} />
                      )}
                    </div>
                  )}

                  <ul className="list">
                    {/* Debt — grouped exactly like the monthly card: tick which debts to pay off. */}
                    {unpaidDebts.length > 0 && (
                      <li style={{ display: "block" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span className="li-main">
                            <span className="alloc__dot" style={{ background: DEBT_COLOR }} />
                            🎯 Pay off debt
                          </span>
                          <strong style={{ minWidth: 78, textAlign: "right" }}>
                            {money(debtPayTotal, currency)}
                          </strong>
                        </div>
                        <div className="alloc__debt">
                          <div className="alloc__debtlist">
                            {unpaidDebts.map((d) => {
                              const checked = !!debtTicked[d.id];
                              return (
                                <div key={d.id} className="alloc__tick">
                                  <input type="checkbox" checked={checked}
                                    onChange={(e) => setDebtTicked((m) => ({ ...m, [d.id]: e.target.checked }))} />
                                  <span>
                                    {d.name} <span className="muted">· {money(d.amount, currency)}</span>
                                  </span>
                                  {checked && (
                                    <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
                                      <span className="muted" style={{ fontSize: 11 }}>pay</span>
                                      <input
                                        className="input alloc__amt"
                                        type="number"
                                        min="0"
                                        step="0.01"
                                        value={payOf(d)}
                                        onChange={(e) => setPayDraft((m) => ({ ...m, [d.id]: e.target.value }))}
                                      />
                                      <span className="muted">€</span>
                                    </span>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                          <div className="li-sub" style={{ marginTop: 6 }}>
                            {debtMoves.length > 0
                              ? `Paying ${money(debtPayTotal, currency)} across ${debtMoves.length} ${debtMoves.length === 1 ? "debt" : "debts"} with this windfall`
                              : "Tick a debt to pay it down with this windfall."}
                          </div>
                        </div>
                      </li>
                    )}

                    {/* Buckets + emergency fund / Steuerrücklage / planned targets */}
                    {rows.map((r) => (
                      <li key={r.key}>
                        <span className="li-main">
                          <span className="alloc__dot" style={{ background: r.color }} />
                          {r.label}
                          {r.hint && (
                            <span className="muted" style={{ fontWeight: 400 }}> · {r.hint}</span>
                          )}
                        </span>
                        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          {r.accountId && (
                            <span className="muted" style={{ fontSize: 12 }}>→ {accById.get(r.accountId)}</span>
                          )}
                          <input
                            className="input alloc__amt"
                            type="number"
                            min="0"
                            step="0.01"
                            disabled={!r.accountId}
                            value={amounts[r.key] ?? String(r.def)}
                            onChange={(e) => setAmounts((m) => ({ ...m, [r.key]: e.target.value }))}
                          />
                          <span className="muted">€</span>
                        </span>
                      </li>
                    ))}

                    {rows.length === 0 && unpaidDebts.length === 0 ? (
                      <li className="muted" style={{ justifyContent: "center" }}>
                        Add buckets in <b>Distribute leftover</b> to split this here.
                      </li>
                    ) : leftover > 0 ? (
                      <li style={{ opacity: 0.75 }}>
                        <span className="li-main muted">Stays in source</span>
                        <span className="muted">{money(leftover, currency)}</span>
                      </li>
                    ) : leftover < 0 ? (
                      <li>
                        <span className="li-main neg">⚠ Over-allocated — moving more than the windfall</span>
                        <span className="neg">{money(-leftover, currency)}</span>
                      </li>
                    ) : null}
                  </ul>

                  <div style={{ marginTop: 12 }}>
                    <button className="btn btn--sm" onClick={() => setApplyOpen(true)} disabled={!canApply}>
                      ✅ Distribute now → {money(allocated, currency)}
                    </button>
                  </div>
                </>
              ) : (
                <div className="empty" style={{ marginTop: 12 }}>
                  Enter an amount above to see how it splits across your buckets.
                </div>
              )}

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
