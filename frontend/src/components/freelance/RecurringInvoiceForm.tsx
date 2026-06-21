import { useState } from "react";
import { apiPatch, apiPost } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import type { ClientOut, ProjectOut, RecurringInvoiceOut } from "../../api/types";
import { LANGUAGES } from "./helpers";

const CADENCES = [
  { value: "weekly", label: "Weekly" },
  { value: "biweekly", label: "Biweekly" },
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
  { value: "yearly", label: "Yearly" },
];

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

// Create or edit a recurring (retainer) template.
export function RecurringInvoiceForm({
  clients,
  rec,
  defaultLanguage,
  onSaved,
  onClose,
}: {
  clients: ClientOut[];
  rec?: RecurringInvoiceOut;
  defaultLanguage?: string;
  onSaved: () => void;
  onClose: () => void;
}) {
  const [clientId, setClientId] = useState(rec?.client_id ?? clients[0]?.id ?? "");
  const [projectId, setProjectId] = useState(rec?.project_id ?? "");
  const [cadence, setCadence] = useState(rec?.cadence ?? "monthly");
  const [mode, setMode] = useState(rec?.mode ?? "flat");
  const [amount, setAmount] = useState(rec?.amount ?? "");
  const [description, setDescription] = useState(rec?.description ?? "");
  const [language, setLanguage] = useState<string>(rec?.language ?? defaultLanguage ?? "de");
  const [nextRun, setNextRun] = useState(rec?.next_run ?? todayISO());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const projectsState = useApi<ProjectOut[]>(clientId ? `/projects?client_id=${clientId}` : "/projects");
  const projects = clientId ? (projectsState.data ?? []).filter((p) => !p.archived || p.id === projectId) : [];

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!clientId) return setError("Pick a client");
    if (mode === "flat" && !(parseFloat(amount) > 0)) return setError("Set a flat amount");
    setBusy(true);
    setError(null);
    const body = {
      client_id: clientId, project_id: projectId || null, cadence, mode,
      amount: amount || "0", description, language, next_run: nextRun, active: rec?.active ?? true,
    };
    try {
      if (rec) await apiPatch(`/recurring-invoices/${rec.id}`, body);
      else await apiPost("/recurring-invoices", body);
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
      <div className="field-row">
        <div className="field">
          <label>Client</label>
          <select className="select" value={clientId}
            onChange={(e) => { setClientId(e.target.value); setProjectId(""); }} required>
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        {projects.length > 0 && (
          <div className="field">
            <label>Project (optional)</label>
            <select className="select" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              <option value="">No project</option>
              {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
        )}
      </div>
      <div className="field-row">
        <div className="field">
          <label>Every</label>
          <select className="select" value={cadence} onChange={(e) => setCadence(e.target.value)}>
            {CADENCES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Bill</label>
          <select className="select" value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="flat">Flat fee (Pauschale)</option>
            <option value="time">Tracked time that period</option>
          </select>
        </div>
        <div className="field" style={{ flex: "0 0 80px" }}>
          <label>Lang.</label>
          <select className="select" value={language} onChange={(e) => setLanguage(e.target.value)}>
            {LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
          </select>
        </div>
      </div>
      {mode === "flat" && (
        <div className="field-row">
          <div className="field" style={{ flex: "0 0 140px" }}>
            <label>Flat amount (€)</label>
            <input className="input" type="number" min="0" step="0.01" value={amount}
              onChange={(e) => setAmount(e.target.value)} placeholder="200.00" />
          </div>
          <div className="field">
            <label>Line description</label>
            <input className="input" value={description} onChange={(e) => setDescription(e.target.value)}
              placeholder="Monatliche Webseiten-Pflege" />
          </div>
        </div>
      )}
      <div className="field" style={{ maxWidth: 200 }}>
        <label>Next invoice on</label>
        <input className="input" type="date" value={nextRun} onChange={(e) => setNextRun(e.target.value)} required />
      </div>
      {error && <div className="error">{error}</div>}
      <div className="form__actions">
        <button type="button" className="btn btn--ghost" onClick={onClose}>Cancel</button>
        <button className="btn" type="submit" disabled={busy}>{busy ? "…" : rec ? "Save" : "Add retainer"}</button>
      </div>
    </form>
  );
}
