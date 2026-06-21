import { useState } from "react";
import { apiPatch, apiPost } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import type { ClientOut, ProjectOut, TimeEntryOut } from "../../api/types";
import { localInputToIso, toLocalInput } from "./helpers";

// Add or edit a time entry by hand (no timer): client, start, duration, description.
export function EntryForm({
  clients,
  entry,
  defaultClientId,
  onSaved,
  onClose,
}: {
  clients: ClientOut[];
  entry?: TimeEntryOut;
  defaultClientId?: string;
  onSaved: () => void;
  onClose: () => void;
}) {
  const [clientId, setClientId] = useState(
    entry?.client_id ?? defaultClientId ?? clients[0]?.id ?? ""
  );
  const [projectId, setProjectId] = useState(entry?.project_id ?? "");
  const [startedAt, setStartedAt] = useState(
    toLocalInput(entry ? new Date(entry.started_at) : new Date())
  );
  const initMin = entry?.minutes ?? 0;
  const [hours, setHours] = useState(String(Math.floor(initMin / 60)));
  const [mins, setMins] = useState(String(initMin % 60));
  const [desc, setDesc] = useState(entry?.description ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const projectsState = useApi<ProjectOut[]>(clientId ? `/projects?client_id=${clientId}` : "/projects");
  const projects = (projectsState.data ?? []).filter((p) => !p.archived || p.id === projectId);

  const onClient = (id: string) => {
    setClientId(id);
    setProjectId(""); // project belongs to a client — reset on change
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const minutes = (parseInt(hours || "0", 10) || 0) * 60 + (parseInt(mins || "0", 10) || 0);
    if (!clientId) return setError("Pick a client");
    if (minutes <= 0) return setError("Duration must be greater than zero");
    setBusy(true);
    setError(null);
    const body = {
      client_id: clientId,
      project_id: projectId || null,
      started_at: localInputToIso(startedAt),
      minutes,
      description: desc || null,
    };
    try {
      if (entry) await apiPatch(`/time-entries/${entry.id}`, body);
      else await apiPost("/time-entries", body);
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
          <select className="select" value={clientId} onChange={(e) => onClient(e.target.value)} required>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
        {projects.length > 0 && (
          <div className="field">
            <label>Project (optional)</label>
            <select className="select" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              <option value="">No project</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
        )}
      </div>
      <div className="field">
        <label>Started</label>
        <input className="input" type="datetime-local" value={startedAt}
          onChange={(e) => setStartedAt(e.target.value)} required />
      </div>
      <div className="field-row">
        <div className="field">
          <label>Hours</label>
          <input className="input" type="number" min="0" step="1" value={hours}
            onChange={(e) => setHours(e.target.value)} />
        </div>
        <div className="field">
          <label>Minutes</label>
          <input className="input" type="number" min="0" max="59" step="1" value={mins}
            onChange={(e) => setMins(e.target.value)} />
        </div>
      </div>
      <div className="field">
        <label>What did you do?</label>
        <textarea className="input" rows={3} placeholder="Description"
          value={desc} onChange={(e) => setDesc(e.target.value)} />
      </div>
      {error && <div className="error">{error}</div>}
      <div className="form__actions">
        <button type="button" className="btn btn--ghost" onClick={onClose}>Cancel</button>
        <button className="btn" type="submit" disabled={busy}>{busy ? "…" : entry ? "Save" : "Add entry"}</button>
      </div>
    </form>
  );
}
