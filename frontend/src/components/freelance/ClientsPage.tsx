import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiDelete, apiPatch, apiPost } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import type { BusinessProfileOut, ClientOut, InvoiceOut, ProjectOut } from "../../api/types";
import { money, num } from "../../lib/format";
import { Card } from "../Card";
import { Async } from "../Async";
import { Modal } from "../Modal";
import { ClientForm } from "./ClientForm";
import { ProjectForm } from "./ProjectForm";
import { fmtHours } from "./helpers";

function budgetClass(used: number, budget: number): string {
  const pct = budget > 0 ? used / budget : 0;
  return pct >= 1 ? " is-over" : pct >= 0.8 ? " is-warn" : "";
}

function ClientBudgetBar({ client }: { client: ClientOut }) {
  if (client.budget_hours == null) return null;
  const budget = num(client.budget_hours);
  const used = num(client.tracked_hours);
  return (
    <div className="client-card__budget">
      <div className="client-card__budget-head">
        <span className="muted">Budget</span>
        <span className="tnum">{fmtHours(client.tracked_hours)} / {fmtHours(client.budget_hours)}</span>
      </div>
      <div className="progress">
        <div className={"progress__bar" + budgetClass(used, budget)}
          style={{ width: `${Math.min(100, (budget > 0 ? used / budget : 0) * 100)}%` }} />
      </div>
    </div>
  );
}

export function ClientsPage() {
  const state = useApi<ClientOut[]>("/clients");
  const projectsState = useApi<ProjectOut[]>("/projects");
  const profile = useApi<BusinessProfileOut>("/business-profile");
  const navigate = useNavigate();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<ClientOut | null>(null);
  const [projModal, setProjModal] = useState<{ client: ClientOut; project?: ProjectOut } | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const projectsByClient = useMemo(() => {
    const m = new Map<string, ProjectOut[]>();
    for (const p of projectsState.data ?? []) {
      const list = m.get(p.client_id) ?? [];
      list.push(p);
      m.set(p.client_id, list);
    }
    return m;
  }, [projectsState.data]);

  const reloadAll = () => { state.reload(); projectsState.reload(); };

  // projectId optional → scope the invoice to a single project
  const createInvoice = async (clientId: string, projectId?: string) => {
    setBusyId(projectId ?? clientId);
    try {
      const inv = await apiPost<InvoiceOut>("/invoices", {
        client_id: clientId, project_id: projectId ?? null,
      });
      navigate(`/business/invoices/${inv.id}`);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to create invoice");
    } finally {
      setBusyId(null);
    }
  };

  const archive = async (client: ClientOut) => {
    await apiPatch(`/clients/${client.id}`, { archived: !client.archived });
    state.reload();
  };
  const remove = async (client: ClientOut) => {
    if (!confirm(`Delete "${client.name}"? This also removes their projects, time entries and invoices.`)) return;
    await apiDelete(`/clients/${client.id}`);
    reloadAll();
  };
  const archiveProject = async (p: ProjectOut) => {
    await apiPatch(`/projects/${p.id}`, { archived: !p.archived });
    projectsState.reload();
  };
  const removeProject = async (p: ProjectOut) => {
    if (!confirm(`Delete project "${p.name}"? Its time entries are kept (un-projected).`)) return;
    await apiDelete(`/projects/${p.id}`);
    reloadAll();
  };

  const action = <button className="btn btn--sm" onClick={() => setAdding(true)}>+ Add client</button>;

  return (
    <Card title="Clients" action={action}>
      <Async state={state}>
        {(clients) => {
          const active = clients.filter((c) => !c.archived);
          const archived = clients.filter((c) => c.archived);
          const shown = showArchived ? clients : active;
          if (clients.length === 0) return <div className="empty">No clients yet. Add one to start tracking.</div>;
          return (
            <>
              <div className="client-grid">
                {shown.map((c) => {
                  const projects = (projectsByClient.get(c.id) ?? []).filter((p) => !p.archived);
                  return (
                    <div key={c.id} className={"client-card" + (c.archived ? " is-archived" : "")}>
                      <div className="client-card__head">
                        <div>
                          <div className="client-card__name">{c.name}</div>
                          <div className="muted" style={{ fontSize: 12 }}>
                            {money(c.hourly_rate)}/h{c.email ? ` · ${c.email}` : ""}
                          </div>
                        </div>
                        {c.archived && <span className="badge">archived</span>}
                      </div>

                      <ClientBudgetBar client={c} />

                      <div className="client-card__stats">
                        <div><div className="muted">Tracked</div><div className="tnum">{fmtHours(c.tracked_hours)}</div></div>
                        <div><div className="muted">Unbilled</div><div className="tnum">{fmtHours(c.unbilled_hours)}</div></div>
                        <div><div className="muted">Unbilled €</div><div className="tnum">{money(c.unbilled_amount)}</div></div>
                      </div>

                      {/* Projects under this client */}
                      <div className="proj-list">
                        <div className="proj-list__head">
                          <span className="muted">Projects</span>
                          {!c.archived && (
                            <button className="btn btn--ghost btn--sm" onClick={() => setProjModal({ client: c })}>
                              + Project
                            </button>
                          )}
                        </div>
                        {projects.length === 0 ? (
                          <div className="muted" style={{ fontSize: 12 }}>No projects — time is billed at the client level.</div>
                        ) : (
                          projects.map((p) => {
                            const budget = p.budget_hours != null ? num(p.budget_hours) : null;
                            const used = num(p.tracked_hours);
                            return (
                              <div key={p.id} className="proj-row">
                                <div className="proj-row__main">
                                  <span className="proj-row__name">{p.name}</span>
                                  <span className="muted proj-row__sub">
                                    {money(p.effective_rate)}/h · {fmtHours(p.unbilled_hours)} unbilled · {money(p.unbilled_amount)}
                                  </span>
                                  {budget != null && (
                                    <div className="progress proj-row__bar">
                                      <div className={"progress__bar" + budgetClass(used, budget)}
                                        style={{ width: `${Math.min(100, (budget > 0 ? used / budget : 0) * 100)}%` }} />
                                    </div>
                                  )}
                                </div>
                                <div className="proj-row__actions">
                                  {num(p.unbilled_hours) > 0 && !c.archived && (
                                    <button className="btn btn--ghost btn--sm" disabled={busyId === p.id}
                                      onClick={() => createInvoice(c.id, p.id)}>
                                      {busyId === p.id ? "…" : "Invoice"}
                                    </button>
                                  )}
                                  <button className="btn btn--ghost btn--sm" onClick={() => setProjModal({ client: c, project: p })}>Edit</button>
                                  <button className="btn btn--ghost btn--sm" onClick={() => archiveProject(p)}>Archive</button>
                                  <button className="btn btn--ghost btn--sm" onClick={() => removeProject(p)}>Delete</button>
                                </div>
                              </div>
                            );
                          })
                        )}
                      </div>

                      <div className="client-card__actions">
                        {num(c.unbilled_hours) > 0 && !c.archived && (
                          <button className="btn btn--sm" disabled={busyId === c.id} onClick={() => createInvoice(c.id)}>
                            {busyId === c.id ? "…" : "Invoice all"}
                          </button>
                        )}
                        <button className="btn btn--ghost btn--sm" onClick={() => setEditing(c)}>Edit</button>
                        <button className="btn btn--ghost btn--sm" onClick={() => archive(c)}>
                          {c.archived ? "Unarchive" : "Archive"}
                        </button>
                        <button className="btn btn--ghost btn--sm" style={{ padding: "4px 8px" }}
                          title="Delete" onClick={() => remove(c)}>×</button>
                      </div>
                    </div>
                  );
                })}
              </div>

              {archived.length > 0 && (
                <button className="btn btn--ghost btn--sm" style={{ marginTop: 14 }}
                  onClick={() => setShowArchived((s) => !s)}>
                  {showArchived ? "Hide" : "Show"} archived ({archived.length})
                </button>
              )}
            </>
          );
        }}
      </Async>

      {adding && (
        <Modal title="Add client" onClose={() => setAdding(false)}>
          <ClientForm defaultRate={profile.data?.default_hourly_rate}
            onSaved={() => state.reload()} onClose={() => setAdding(false)} />
        </Modal>
      )}
      {editing && (
        <Modal title="Edit client" onClose={() => setEditing(null)}>
          <ClientForm client={editing} onSaved={() => state.reload()} onClose={() => setEditing(null)} />
        </Modal>
      )}
      {projModal && (
        <Modal title={projModal.project ? "Edit project" : `New project · ${projModal.client.name}`}
          onClose={() => setProjModal(null)}>
          <ProjectForm clientId={projModal.client.id} clientRate={projModal.client.hourly_rate}
            project={projModal.project} onSaved={() => projectsState.reload()} onClose={() => setProjModal(null)} />
        </Modal>
      )}
    </Card>
  );
}
