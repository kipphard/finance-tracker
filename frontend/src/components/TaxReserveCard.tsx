import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiPatch } from "../api/client";
import type { AccountOut, TaxReserveOut } from "../api/types";
import { money, num } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

// Steuerrücklage: how much income tax to keep aside for the freelance profit earned so far
// this year, vs. how much actually is. Owed is computed from the §32a EÜR estimate; the
// set-aside is a designated account's balance (earmarked out of runway) or a notional amount.
export function TaxReserveCard({ className }: { className?: string }) {
  const state = useApi<TaxReserveOut>("/tax-reserve");
  const accountsApi = useApi<AccountOut[]>("/accounts");
  const [busy, setBusy] = useState(false);

  const patch = async (body: Record<string, unknown>) => {
    setBusy(true);
    try {
      await apiPatch("/tax-reserve", body);
      state.reload();
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Steuerrücklage" className={className}>
      <Async state={state}>
        {(r) => {
          const pct = num(r.funded_pct);
          const gap = num(r.gap);
          const surplus = num(r.surplus);
          const owed = num(r.owed_ytd);
          const accounts = accountsApi.data ?? [];
          return (
            <>
              <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>
                Einkommensteuer-Rücklage für {r.year} — geschätzt aus deinem EÜR-Gewinn.
              </div>

              <div className="metric-row">
                <div className="metric-block">
                  <div className="label">Zurückzulegen (YTD)</div>
                  <div className="value">{money(r.owed_ytd)}</div>
                </div>
                <div className="metric-block">
                  <div className="label">Bereits zurückgelegt</div>
                  <div className="value">{money(r.reserve)}</div>
                </div>
                <div className="metric-block">
                  <div className="label">{surplus > 0 ? "Puffer" : "Fehlt noch"}</div>
                  <div className={"value " + (gap > 0 ? "neg" : "pos")}>
                    {gap > 0 ? money(r.gap) : surplus > 0 ? money(r.surplus) : "—"}
                  </div>
                </div>
              </div>

              <div className="progress" style={{ margin: "12px 0 8px" }}>
                <div className="progress__bar"
                  style={{ width: Math.min(100, pct) + "%", background: gap <= 0 ? "#10b981" : undefined }} />
              </div>

              <div className="muted" style={{ fontSize: 11, marginBottom: 12 }}>
                {pct.toFixed(0)}% gedeckt
                {owed > 0 && <> · Rücklagequote ~{num(r.effective_rate).toFixed(0)}% der Einnahmen</>}
                {num(r.recommended_monthly) > 0 && (
                  <>
                    {" "}· lege ~<strong>{money(r.recommended_monthly)}</strong>/Monat zurück, um {r.year}{" "}
                    voll gedeckt zu sein
                  </>
                )}
              </div>

              <div className="ef__row">
                <span className="muted" style={{ fontSize: 12 }}>Rücklage-Konto</span>
                <select
                  className="select"
                  style={{ maxWidth: 220 }}
                  disabled={busy}
                  value={r.reserve_account_id ?? ""}
                  onChange={(e) => patch({ reserve_account_id: e.target.value || null })}
                >
                  <option value="">Manuell erfassen</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </select>
              </div>

              {!r.has_account && (
                <div className="ef__row" style={{ marginTop: 8 }}>
                  <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span className="muted" style={{ fontSize: 12 }}>Zurückgelegt</span>
                    <input className="input alloc__amt" type="number" min="0" step="50" disabled={busy}
                      defaultValue={String(num(r.current_amount))}
                      onBlur={(e) => patch({ current_amount: e.target.value || "0" })} />
                    <span className="muted">€</span>
                  </span>
                </div>
              )}

              <div className="muted" style={{ fontSize: 11, marginTop: 10 }}>
                {r.has_account
                  ? "Das Rücklage-Konto ist zweckgebunden — aus dem Cash runway ausgenommen, damit du das Geld des Finanzamts nicht als verfügbar zählst."
                  : "Verknüpfe ein Konto, damit der Kontostand automatisch als Rücklage zählt (und aus dem Runway ausgenommen wird)."}
                {" "}Fließt vorab in die <b>Distribute leftover</b>-Aufteilung. Grobe Schätzung,
                keine Steuerberatung.
              </div>
            </>
          );
        }}
      </Async>
    </Card>
  );
}
