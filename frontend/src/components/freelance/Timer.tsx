import { useEffect, useState } from "react";
import { apiPatch, apiPost } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import type { ClientOut, ProjectOut, TimeEntryOut } from "../../api/types";
import { fmtClock } from "./helpers";

// Start/stop timer against a client (and optional project). The running entry lives
// server-side, so a running timer survives a page reload (GET /time-entries/running).
export function Timer({ clients }: { clients: ClientOut[] }) {
  const running = useApi<TimeEntryOut | null>("/time-entries/running");
  const [clientId, setClientId] = useState("");
  const [projectId, setProjectId] = useState("");
  const [desc, setDesc] = useState("");
  const [now, setNow] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const entry = running.data;
  const projectsState = useApi<ProjectOut[]>(clientId ? `/projects?client_id=${clientId}` : "/projects");
  const projects = (projectsState.data ?? []).filter((p) => !p.archived || p.id === projectId);

  // Default the client picker once clients load.
  useEffect(() => {
    if (!clientId && clients.length) setClientId(clients[0].id);
  }, [clients, clientId]);

  // Adopt the running entry's client/project/description on recovery.
  useEffect(() => {
    if (entry) {
      setClientId(entry.client_id);
      setProjectId(entry.project_id ?? "");
      setDesc(entry.description ?? "");
    }
  }, [entry?.id]);

  // Tick the live clock once a second while running.
  useEffect(() => {
    if (!entry) return;
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [entry?.id]);

  const onClient = (id: string) => {
    setClientId(id);
    setProjectId(""); // project belongs to a client — reset when the client changes
  };

  const start = async () => {
    if (!clientId) return;
    setBusy(true);
    setError(null);
    try {
      await apiPost("/time-entries/start", {
        client_id: clientId, project_id: projectId || null, description: desc || null,
      });
      running.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    if (!entry) return;
    setBusy(true);
    setError(null);
    try {
      if ((desc || "") !== (entry.description ?? "")) {
        await apiPatch(`/time-entries/${entry.id}`, { description: desc || null });
      }
      await apiPost(`/time-entries/${entry.id}/stop`);
      setDesc("");
      running.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  const elapsed = entry ? now - new Date(entry.started_at).getTime() : 0;
  const clientName = entry ? clients.find((c) => c.id === entry.client_id)?.name : null;
  const projectName = entry?.project_id
    ? (projectsState.data ?? []).find((p) => p.id === entry.project_id)?.name
    : null;

  return (
    <div className={"timer" + (entry ? " timer--running" : "")}>
      <div className="timer__clock tnum">{fmtClock(elapsed)}</div>

      {entry ? (
        <span className="muted timer__tracking">
          Tracking{clientName ? <> · <strong>{clientName}</strong></> : null}
          {projectName ? <> · {projectName}</> : null}
        </span>
      ) : clients.length === 0 ? (
        <span className="muted timer__tracking">Add a client first, then start tracking.</span>
      ) : (
        <>
          <select className="select timer__client" value={clientId} onChange={(e) => onClient(e.target.value)}>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          {projects.length > 0 && (
            <select className="select timer__project" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              <option value="">No project</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          )}
        </>
      )}

      <input
        className="input timer__desc"
        placeholder="What are you working on?"
        value={desc}
        onChange={(e) => setDesc(e.target.value)}
      />

      {entry ? (
        <button className="btn btn--stop" onClick={stop} disabled={busy}>■ Stop</button>
      ) : (
        <button className="btn btn--start" onClick={start} disabled={busy || !clientId}>▶ Start</button>
      )}

      {error && <div className="error timer__error">{error}</div>}
    </div>
  );
}
