import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiPatch } from "../api/client";
import type { AccountOut, EmergencyFundOut } from "../api/types";
import { money, num } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

export function EmergencyFundCard({ className }: { className?: string }) {
  const state = useApi<EmergencyFundOut>("/emergency-fund");
  const accounts = useApi<AccountOut[]>("/accounts");
  const [busy, setBusy] = useState(false);

  const patch = async (body: Record<string, unknown>) => {
    setBusy(true);
    try {
      await apiPatch("/emergency-fund", body);
      state.reload();
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Emergency fund" className={className}>
      <Async state={state}>
        {(f) => {
          const custom = f.target_amount !== null;
          const pct = num(f.funded_pct);
          const gap = num(f.gap);
          return (
            <>
              <div className="ef__row">
                <span className="muted" style={{ fontSize: 12 }}>Target</span>
                {custom ? (
                  <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <input className="input alloc__amt" type="number" min="0" step="50" disabled={busy}
                      defaultValue={String(num(f.target_amount ?? 0))}
                      onBlur={(e) => patch({ target_amount: e.target.value || "0" })} />
                    <span className="muted">€</span>
                    <button className="btn btn--ghost btn--sm" onClick={() => patch({ target_amount: null })}>
                      × fixed
                    </button>
                  </span>
                ) : (
                  <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <input className="input alloc__pct" type="number" min="0" step="1" disabled={busy}
                      defaultValue={String(f.target_months)}
                      onBlur={(e) => patch({ target_months: parseInt(e.target.value || "0", 10) })} />
                    <span className="muted">× fixed ({money(f.monthly_fixed)})</span>
                    <button className="btn btn--ghost btn--sm"
                      onClick={() => patch({ target_amount: String(num(f.target) || 0) })}>
                      custom
                    </button>
                  </span>
                )}
              </div>
              <div className="ef__target">
                {money(f.target)}{" "}
                <span className="muted" style={{ fontSize: 12, fontWeight: 400 }}>goal</span>
              </div>

              <div className="progress" style={{ margin: "12px 0 8px" }}>
                <div className="progress__bar"
                  style={{ width: Math.min(100, pct) + "%", background: gap <= 0 ? "#10b981" : undefined }} />
              </div>

              <div className="ef__row">
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span className="muted" style={{ fontSize: 12 }}>Saved</span>
                  {f.account_id ? (
                    <span style={{ fontWeight: 600 }}>{money(f.current_amount)}</span>
                  ) : (
                    <>
                      <input className="input alloc__amt" type="number" min="0" step="50" disabled={busy}
                        defaultValue={String(num(f.current_amount))}
                        onBlur={(e) => patch({ current_amount: e.target.value || "0" })} />
                      <span className="muted">€</span>
                    </>
                  )}
                </span>
                <span className={gap > 0 ? "neg" : "pos"} style={{ fontWeight: 600 }}>
                  {gap > 0 ? `${money(f.gap)} to go` : "Fully funded 🎉"}
                </span>
              </div>

              <div className="ef__row" style={{ marginTop: 8 }}>
                <span className="muted" style={{ fontSize: 12 }}>Held in</span>
                <select className="select" disabled={busy} value={f.account_id ?? ""}
                  onChange={(e) => patch({ account_id: e.target.value || null })}
                  title="Link an account — its balance becomes 'saved', and 'Apply this month' pays into it">
                  <option value="">— not linked (track manually) —</option>
                  {(accounts.data ?? []).map((a) => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </select>
              </div>

              {f.shared_with && (
                <div className="ef__row" style={{ marginTop: 8 }}>
                  <span className="muted" style={{ fontSize: 12 }}>
                    ⚖ Shares this account with <b>{f.shared_with}</b> — fill order
                  </span>
                  <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <input className="input alloc__pct" type="number" min="0" step="1" disabled={busy}
                      defaultValue={String(f.account_priority)} key={f.account_priority}
                      onBlur={(e) => patch({ account_priority: parseInt(e.target.value || "100", 10) })}
                      title="Lower fills first; the first goal is capped at its target, the other gets the remainder" />
                    <span className="muted" style={{ fontSize: 11 }}>lower = first</span>
                  </span>
                </div>
              )}

              <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>
                {pct.toFixed(0)}% funded · {f.target_months}× your monthly fixed costs is a common buffer.
                {f.account_id && " Saved follows the linked account's balance."}
              </div>
            </>
          );
        }}
      </Async>
    </Card>
  );
}
