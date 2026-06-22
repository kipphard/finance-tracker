import { useMemo, useState } from "react";
import { apiDelete } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import type { ClientOut, ProjectOut, TimeEntryOut } from "../../api/types";
import { Card } from "../Card";
import { Async } from "../Async";
import { Modal } from "../Modal";
import { Pager, paginate, usePageSize } from "../Pager";
import { Timer } from "./Timer";
import { EntryForm } from "./EntryForm";
import { fmtDateTime, fmtDuration } from "./helpers";

export function TimePage() {
  const clientsState = useApi<ClientOut[]>("/clients");
  const projectsState = useApi<ProjectOut[]>("/projects");
  const [filter, setFilter] = useState("");
  const [projectFilter, setProjectFilter] = useState("");
  const query = [filter && `client_id=${filter}`, projectFilter && `project_id=${projectFilter}`]
    .filter(Boolean)
    .join("&");
  const entriesState = useApi<TimeEntryOut[]>("/time-entries" + (query ? `?${query}` : ""));
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<TimeEntryOut | null>(null);
  const [page, setPage] = useState(0);
  const size = usePageSize();

  const clients = clientsState.data ?? [];
  const allProjects = projectsState.data ?? [];
  const activeClients = clients.filter((c) => !c.archived);
  const nameOf = useMemo(() => {
    const m = new Map(clients.map((c) => [c.id, c.name]));
    return (id: string) => m.get(id) ?? "—";
  }, [clients]);
  const projNameOf = useMemo(() => {
    const m = new Map(allProjects.map((p) => [p.id, p.name]));
    return (id: string | null) => (id ? m.get(id) ?? null : null);
  }, [allProjects]);
  const filterProjects = allProjects.filter((p) => !filter || p.client_id === filter);

  const remove = async (id: string) => {
    await apiDelete(`/time-entries/${id}`);
    entriesState.reload();
  };

  const action = (
    <button className="btn btn--sm" disabled={activeClients.length === 0} onClick={() => setAdding(true)}>
      + Manual entry
    </button>
  );

  return (
    <>
      <Async state={clientsState}>{() => <Timer clients={activeClients} />}</Async>

      <Card title="Time entries" action={action}>
        <div className="toolbar">
          <select className="select" value={filter}
            onChange={(e) => { setFilter(e.target.value); setProjectFilter(""); setPage(0); }}>
            <option value="">All clients</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          {filterProjects.length > 0 && (
            <select className="select" value={projectFilter}
              onChange={(e) => { setProjectFilter(e.target.value); setPage(0); }}>
              <option value="">All projects</option>
              {filterProjects.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          )}
        </div>

        <Async state={entriesState}>
          {(all) => {
            const entries = [...all].sort(
              (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
            );
            if (entries.length === 0) return <div className="empty">No time tracked yet.</div>;
            const { slice, pages, page: p } = paginate(entries, page, size);
            return (
              <>
                <div className="table-scroll">
                <table className="ftable">
                  <thead>
                    <tr>
                      <th>When</th>
                      <th>Client</th>
                      <th>Project</th>
                      <th className="ftable__num">Duration</th>
                      <th>Description</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {slice.map((e) => {
                      const running = e.ended_at == null;
                      const billed = e.invoice_id != null;
                      return (
                        <tr key={e.id}>
                          <td>{fmtDateTime(e.started_at)}</td>
                          <td>{nameOf(e.client_id)}</td>
                          <td>{projNameOf(e.project_id) ?? <span className="muted">—</span>}</td>
                          <td className="ftable__num tnum">
                            {running ? <span className="badge badge--recurring">running</span> : fmtDuration(e.minutes)}
                          </td>
                          <td className="ftable__desc">
                            {e.description || <span className="muted">—</span>}
                          </td>
                          <td className="ftable__actions">
                            {billed ? (
                              <span className="badge">billed</span>
                            ) : running ? null : (
                              <span className="row-actions">
                                <button className="btn btn--ghost btn--sm" onClick={() => setEditing(e)}>Edit</button>
                                <button className="btn btn--ghost btn--sm" style={{ padding: "2px 7px" }}
                                  title="Delete" onClick={() => remove(e.id)}>×</button>
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                </div>
                <Pager page={p} pages={pages} total={entries.length} onPage={setPage} />
              </>
            );
          }}
        </Async>
      </Card>

      {adding && (
        <Modal title="Add time entry" onClose={() => setAdding(false)}>
          <EntryForm clients={activeClients} defaultClientId={filter || undefined}
            onSaved={() => entriesState.reload()} onClose={() => setAdding(false)} />
        </Modal>
      )}
      {editing && (
        <Modal title="Edit time entry" onClose={() => setEditing(null)}>
          <EntryForm clients={activeClients} entry={editing}
            onSaved={() => entriesState.reload()} onClose={() => setEditing(null)} />
        </Modal>
      )}
    </>
  );
}
