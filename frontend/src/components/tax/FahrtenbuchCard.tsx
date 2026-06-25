import { useState } from "react";
import { apiDelete, apiPost } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import type { ClientOut, TaxProfileOut, TripOut } from "../../api/types";
import { money, num, shortDate } from "../../lib/format";
import { Card } from "../Card";
import { Async } from "../Async";

// Per-trip mileage log. The summed km for the year flow into the EÜR's Reisekosten (overriding
// the single manual business-km figure whenever trips are logged), so editing here updates the EÜR.
export function FahrtenbuchCard({ year }: { year: number }) {
  const trips = useApi<TripOut[]>(`/trips?year=${year}`);
  const clients = useApi<ClientOut[]>("/clients");
  const profile = useApi<TaxProfileOut>("/tax/profile");
  const clientName = (id: string | null) =>
    id ? clients.data?.find((c) => c.id === id)?.name ?? "—" : "";

  const [date, setDate] = useState(`${year}-01-01`);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [km, setKm] = useState("");
  const [purpose, setPurpose] = useState("");
  const [clientId, setClientId] = useState("");
  const [busy, setBusy] = useState(false);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await apiPost("/trips", {
        date, km, from_place: from, to_place: to, purpose,
        client_id: clientId || null,
      });
      setFrom(""); setTo(""); setKm(""); setPurpose(""); setClientId("");
      trips.reload();
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    await apiDelete(`/trips/${id}`);
    trips.reload();
  };

  return (
    <Card title="🚗 Fahrtenbuch">
      <Async state={trips}>
        {(list) => {
          const totalKm = list.reduce((s, t) => s + num(t.km), 0);
          const rate = num(profile.data?.km_rate ?? "0");
          return (
            <>
              {list.length === 0 ? (
                <div className="empty">No trips logged for {year} yet — add one below.</div>
              ) : (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Route</th>
                        <th>Purpose</th>
                        <th className="amount">km</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {list.map((t) => (
                        <tr key={t.id}>
                          <td>{shortDate(t.date)}</td>
                          <td>
                            {t.from_place || t.to_place ? `${t.from_place} → ${t.to_place}` : "—"}
                            {t.client_id && <span className="muted"> · {clientName(t.client_id)}</span>}
                          </td>
                          <td>{t.purpose || "—"}</td>
                          <td className="amount tnum">{num(t.km).toFixed(1)}</td>
                          <td className="amount">
                            <button className="btn btn--ghost btn--sm" style={{ padding: "2px 8px" }}
                              onClick={() => remove(t.id)} title="Delete trip">✕</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <form className="form" onSubmit={add} style={{ marginTop: 12 }}>
                <div className="field-row">
                  <div className="field" style={{ flex: "0 0 150px" }}>
                    <label>Date</label>
                    <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
                  </div>
                  <div className="field" style={{ flex: "0 0 110px" }}>
                    <label>km</label>
                    <input className="input" type="number" min="0" step="0.1" placeholder="0"
                      value={km} onChange={(e) => setKm(e.target.value)} required />
                  </div>
                  <div className="field">
                    <label>From</label>
                    <input className="input" placeholder="e.g. Köln" value={from} onChange={(e) => setFrom(e.target.value)} />
                  </div>
                  <div className="field">
                    <label>To</label>
                    <input className="input" placeholder="e.g. Bonn" value={to} onChange={(e) => setTo(e.target.value)} />
                  </div>
                </div>
                <div className="field-row">
                  <div className="field">
                    <label>Purpose</label>
                    <input className="input" placeholder="e.g. Kundentermin" value={purpose} onChange={(e) => setPurpose(e.target.value)} />
                  </div>
                  <div className="field" style={{ flex: "0 0 200px" }}>
                    <label>Client (optional)</label>
                    <select className="select" value={clientId} onChange={(e) => setClientId(e.target.value)}>
                      <option value="">—</option>
                      {(clients.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                  </div>
                  <div className="field" style={{ flex: "0 0 auto", alignSelf: "flex-end" }}>
                    <button className="btn" type="submit" disabled={busy || !km}>{busy ? "…" : "+ Add trip"}</button>
                  </div>
                </div>
              </form>

              <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
                <strong>{totalKm.toFixed(1)} km</strong> logged for {year}
                {rate > 0 && <> · Reisekosten ≈ <strong>{money(totalKm * rate)}</strong> ({money(rate)}/km)</>} —
                flows into the EÜR above, overriding the manual business-km figure.
              </div>
            </>
          );
        }}
      </Async>
    </Card>
  );
}
