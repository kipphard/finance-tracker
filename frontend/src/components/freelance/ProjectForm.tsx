import { useState } from "react";
import { apiPatch, apiPost } from "../../api/client";
import type { ProjectOut } from "../../api/types";

// Add or edit a project under a client. Rate/budget are optional overrides of the client's.
export function ProjectForm({
  clientId,
  clientRate,
  project,
  onSaved,
  onClose,
}: {
  clientId: string;
  clientRate?: string;
  project?: ProjectOut;
  onSaved: () => void;
  onClose: () => void;
}) {
  const [name, setName] = useState(project?.name ?? "");
  const [rate, setRate] = useState(project?.hourly_rate ?? "");
  const [budget, setBudget] = useState(project?.budget_hours ?? "");
  const [notes, setNotes] = useState(project?.notes ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body = {
      name,
      hourly_rate: rate === "" ? null : rate,
      budget_hours: budget === "" ? null : budget,
      notes: notes || null,
    };
    try {
      if (project) await apiPatch(`/projects/${project.id}`, body);
      else await apiPost("/projects", { client_id: clientId, ...body });
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
        <label>Project name</label>
        <input className="input" value={name} onChange={(e) => setName(e.target.value)} required autoFocus
          placeholder="e.g. Website relaunch" />
      </div>
      <div className="field-row">
        <div className="field">
          <label>Hourly rate (€)</label>
          <input className="input" type="number" min="0" step="0.01" value={rate}
            onChange={(e) => setRate(e.target.value)}
            placeholder={clientRate ? `inherits ${clientRate}` : "inherits client rate"} />
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
        <button className="btn" type="submit" disabled={busy}>{busy ? "…" : project ? "Save" : "Add project"}</button>
      </div>
    </form>
  );
}
