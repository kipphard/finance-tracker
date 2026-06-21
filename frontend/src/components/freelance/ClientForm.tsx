import { useState } from "react";
import { apiPatch, apiPost } from "../../api/client";
import type { ClientOut } from "../../api/types";

// Add or edit a client (used for the invoice recipient + hourly rate + budget).
export function ClientForm({
  client,
  defaultRate,
  onSaved,
  onClose,
}: {
  client?: ClientOut;
  defaultRate?: string;
  onSaved: () => void;
  onClose: () => void;
}) {
  const [name, setName] = useState(client?.name ?? "");
  const [email, setEmail] = useState(client?.email ?? "");
  const [address, setAddress] = useState(client?.address ?? "");
  const [rate, setRate] = useState(client?.hourly_rate ?? defaultRate ?? "");
  const [budget, setBudget] = useState(client?.budget_hours ?? "");
  const [notes, setNotes] = useState(client?.notes ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body = {
      name,
      email: email || null,
      address,
      hourly_rate: rate || "0",
      budget_hours: budget === "" ? null : budget,
      notes: notes || null,
    };
    try {
      if (client) await apiPatch(`/clients/${client.id}`, body);
      else await apiPost("/clients", body);
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="form" onSubmit={submit}>
      <div className="field">
        <label>Name</label>
        <input className="input" value={name} onChange={(e) => setName(e.target.value)} required autoFocus
          placeholder="Client / company name" />
      </div>
      <div className="field">
        <label>Email (optional)</label>
        <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      </div>
      <div className="field">
        <label>Invoice address</label>
        <textarea className="input" rows={3} value={address} onChange={(e) => setAddress(e.target.value)}
          placeholder={"Company GmbH\nStreet 1\n12345 City"} />
      </div>
      <div className="field-row">
        <div className="field">
          <label>Hourly rate (€)</label>
          <input className="input" type="number" min="0" step="0.01" value={rate}
            onChange={(e) => setRate(e.target.value)} placeholder="45.00" />
        </div>
        <div className="field">
          <label>Budget hours (optional)</label>
          <input className="input" type="number" min="0" step="0.25" value={budget}
            onChange={(e) => setBudget(e.target.value)} placeholder="—" />
        </div>
      </div>
      <div className="field">
        <label>Notes (optional)</label>
        <textarea className="input" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </div>
      {error && <div className="error">{error}</div>}
      <div className="form__actions">
        <button type="button" className="btn btn--ghost" onClick={onClose}>Cancel</button>
        <button className="btn" type="submit" disabled={busy}>{busy ? "…" : client ? "Save" : "Add client"}</button>
      </div>
    </form>
  );
}
