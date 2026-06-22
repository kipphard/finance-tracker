import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiDelete, apiPatch, apiPost } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import type {
  BusinessProfileOut, ClientOut, InvoiceOut, ProjectOut, RecurringInvoiceOut, TimeEntryOut,
} from "../../api/types";
import { money, num, shortDate } from "../../lib/format";
import { Card } from "../Card";
import { Async } from "../Async";
import { Modal } from "../Modal";
import { RecurringInvoiceForm } from "./RecurringInvoiceForm";
import { LANGUAGES, fmtDuration } from "./helpers";

function RecurringInvoicesCard() {
  const state = useApi<RecurringInvoiceOut[]>("/recurring-invoices");
  const clientsState = useApi<ClientOut[]>("/clients");
  const profile = useApi<BusinessProfileOut>("/business-profile");
  const [editing, setEditing] = useState<RecurringInvoiceOut | "new" | null>(null);

  const clients = (clientsState.data ?? []).filter((c) => !c.archived);
  const toggle = async (r: RecurringInvoiceOut) => {
    await apiPatch(`/recurring-invoices/${r.id}`, { active: !r.active });
    state.reload();
  };
  const remove = async (r: RecurringInvoiceOut) => {
    if (!confirm("Delete this retainer? (existing invoices are kept)")) return;
    await apiDelete(`/recurring-invoices/${r.id}`);
    state.reload();
  };

  const action = (
    <button className="btn btn--sm" disabled={clients.length === 0}
      onClick={() => setEditing("new")}>+ Retainer</button>
  );

  return (
    <Card title="Recurring invoices (retainers)" action={action} className="recurring-card">
      <Async state={state}>
        {(recs) => recs.length === 0 ? (
          <div className="empty">No retainers. Add one to auto-draft an invoice each period.</div>
        ) : (
          <div className="table-scroll">
          <table className="ftable">
            <thead>
              <tr>
                <th>Client</th><th>Every</th><th>Bills</th>
                <th className="ftable__num">Next</th><th></th>
              </tr>
            </thead>
            <tbody>
              {recs.map((r) => (
                <tr key={r.id} style={{ opacity: r.active ? 1 : 0.5 }}>
                  <td>{r.client_name ?? "—"}{r.project_name ? <span className="muted"> · {r.project_name}</span> : null}</td>
                  <td>{r.cadence}</td>
                  <td>{r.mode === "flat" ? `${money(r.amount)} pauschal` : "tracked time"}</td>
                  <td className="ftable__num">{shortDate(r.next_run)}</td>
                  <td className="ftable__actions">
                    <span className="row-actions">
                      <button className="btn btn--ghost btn--sm" onClick={() => setEditing(r)}>Edit</button>
                      <button className="btn btn--ghost btn--sm" onClick={() => toggle(r)}>
                        {r.active ? "Pause" : "Resume"}
                      </button>
                      <button className="btn btn--ghost btn--sm" style={{ padding: "2px 7px" }}
                        title="Delete" onClick={() => remove(r)}>×</button>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </Async>
      {editing && (
        <Modal title={editing === "new" ? "New retainer" : "Edit retainer"} className="modal--md"
          onClose={() => setEditing(null)}>
          <RecurringInvoiceForm clients={clients} rec={editing === "new" ? undefined : editing}
            defaultLanguage={profile.data?.default_language}
            onSaved={() => state.reload()} onClose={() => setEditing(null)} />
        </Modal>
      )}
    </Card>
  );
}

const STATUS_CLASS: Record<string, string> = {
  draft: "badge",
  sent: "badge badge--fixed",
  paid: "badge badge--tag",
};

function NewInvoiceForm({ onClose }: { onClose: () => void }) {
  const clients = useApi<ClientOut[]>("/clients");
  const profile = useApi<BusinessProfileOut>("/business-profile");
  const navigate = useNavigate();
  const [clientId, setClientId] = useState("");
  const [projectId, setProjectId] = useState("");
  const [language, setLanguage] = useState<string>("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const active = (clients.data ?? []).filter((c) => !c.archived);
  const projects = useApi<ProjectOut[]>(clientId ? `/projects?client_id=${clientId}` : "/projects");
  const clientProjects = clientId ? (projects.data ?? []).filter((p) => !p.archived) : [];
  const lang = language || profile.data?.default_language || "de";

  // Unbilled time for the chosen client/project/date-range — the lines we can bill.
  const entryQuery = [
    "unbilled=true",
    clientId && `client_id=${clientId}`,
    projectId && `project_id=${projectId}`,
    from && `from=${from}`,
    to && `to=${to}`,
  ].filter(Boolean).join("&");
  const entriesState = useApi<TimeEntryOut[]>(clientId ? `/time-entries?${entryQuery}` : "/time-entries?unbilled=true");
  const entries = useMemo(
    () => clientId
      ? [...(entriesState.data ?? [])].sort((a, b) => a.started_at.localeCompare(b.started_at))
      : [],
    [entriesState.data, clientId]
  );
  const idsKey = entries.map((e) => e.id).join(",");
  // Default to billing everything shown; the user can untick lines to exclude them.
  useEffect(() => { setSelected(new Set(entries.map((e) => e.id))); }, [idsKey]);

  const client = active.find((c) => c.id === clientId);
  const rateOf = (e: TimeEntryOut) => {
    if (e.project_id) {
      const p = (projects.data ?? []).find((pp) => pp.id === e.project_id);
      if (p && p.hourly_rate != null) return num(p.hourly_rate);
    }
    return num(client?.hourly_rate ?? 0);
  };
  const amountOf = (e: TimeEntryOut) => (e.minutes / 60) * rateOf(e);

  const toggle = (id: string) =>
    setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const allSelected = entries.length > 0 && entries.every((e) => selected.has(e.id));
  const toggleAll = () =>
    setSelected(allSelected ? new Set() : new Set(entries.map((e) => e.id)));

  const chosen = entries.filter((e) => selected.has(e.id));
  const totalMin = chosen.reduce((s, e) => s + e.minutes, 0);
  const totalAmt = chosen.reduce((s, e) => s + amountOf(e), 0);

  const onClient = (id: string) => {
    setClientId(id);
    setProjectId("");
    setFrom("");
    setTo("");
  };

  const create = async (body: Record<string, unknown>) => {
    setBusy(true);
    setError(null);
    try {
      const inv = await apiPost<InvoiceOut>("/invoices", {
        client_id: clientId, project_id: projectId || null, language: lang, ...body,
      });
      onClose();
      navigate(`/freelance/invoices/${inv.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!clientId) return setError("Pick a client");
    if (chosen.length === 0) return setError("Select at least one entry to bill");
    await create({ entry_ids: chosen.map((en) => en.id) });
  };

  const createBlank = async () => {
    if (!clientId) return setError("Pick a client");
    await create({ blank: true });
  };

  return (
    <form className="form" onSubmit={submit}>
      <div className="field-row">
        <div className="field">
          <label>Client</label>
          <select className="select" value={clientId} onChange={(e) => onClient(e.target.value)} required>
            <option value="">Select a client…</option>
            {active.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
        {clientProjects.length > 0 && (
          <div className="field">
            <label>Project</label>
            <select className="select" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              <option value="">Whole client</option>
              {clientProjects.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
        )}
        <div className="field" style={{ flex: "0 0 80px" }}>
          <label>Lang.</label>
          <select className="select" value={lang} onChange={(e) => setLanguage(e.target.value)}>
            {LANGUAGES.map((l) => (
              <option key={l.value} value={l.value}>{l.label}</option>
            ))}
          </select>
        </div>
      </div>

      {clientId && (
        <>
          <div className="field-row">
            <div className="field">
              <label>From (optional)</label>
              <input className="input" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
            </div>
            <div className="field">
              <label>To (optional)</label>
              <input className="input" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
            </div>
          </div>

          <Async state={entriesState}>
            {() => (entries.length === 0 ? (
              <div className="empty">No unbilled time for this selection.</div>
            ) : (
              <div className="inv-pick">
                <div className="inv-pick__head">
                  <label className="check" style={{ fontWeight: 600 }}>
                    <input type="checkbox" checked={allSelected} onChange={toggleAll} />
                    <span>Unbilled entries</span>
                  </label>
                  <span className="muted">{chosen.length}/{entries.length}</span>
                </div>
                <div className="inv-pick__list">
                  {entries.map((e) => (
                    <label key={e.id} className="inv-pick__row">
                      <input type="checkbox" checked={selected.has(e.id)} onChange={() => toggle(e.id)} />
                      <span className="inv-pick__date">{shortDate(e.started_at)}</span>
                      <span className="inv-pick__desc">{e.description || "—"}</span>
                      <span className="tnum inv-pick__dur">{fmtDuration(e.minutes)}</span>
                      <span className="tnum inv-pick__amt">{money(amountOf(e))}</span>
                    </label>
                  ))}
                </div>
                <div className="inv-pick__foot">
                  <span className="muted">{chosen.length} selected · {fmtDuration(totalMin)}</span>
                  <span className="tnum" style={{ fontWeight: 700 }}>{money(totalAmt)}</span>
                </div>
              </div>
            ))}
          </Async>
        </>
      )}

      {clientId && (
        <div className="muted" style={{ fontSize: 12 }}>
          Or start a <strong>blank invoice</strong> (no tracked time) to bill a flat project/service fee.
        </div>
      )}
      {error && <div className="error">{error}</div>}
      <div className="form__actions">
        <button type="button" className="btn btn--ghost" onClick={onClose}>Cancel</button>
        <button type="button" className="btn btn--ghost" disabled={busy || !clientId} onClick={createBlank}>
          {busy ? "…" : "Blank invoice"}
        </button>
        <button className="btn" type="submit" disabled={busy || chosen.length === 0}>
          {busy ? "…" : "Create from time"}
        </button>
      </div>
    </form>
  );
}

export function InvoicesPage() {
  const state = useApi<InvoiceOut[]>("/invoices");
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);

  // generate any due retainer drafts on load (catch-up + advance), then the list refreshes
  useEffect(() => { apiPost("/recurring-invoices/run").catch(() => {}); }, []);

  const action = (
    <button className="btn btn--sm" onClick={() => setCreating(true)}>+ New invoice</button>
  );

  return (
    <>
      <RecurringInvoicesCard />
      <Card title="Invoices" action={action} className="invoices-card">
      <Async state={state}>
        {(invoices) => {
          if (invoices.length === 0) return <div className="empty">No invoices yet.</div>;
          const sorted = [...invoices].sort(
            (a, b) => new Date(b.issue_date).getTime() - new Date(a.issue_date).getTime()
          );
          return (
            <div className="table-scroll">
            <table className="ftable ftable--click">
              <thead>
                <tr>
                  <th>No.</th>
                  <th>Client</th>
                  <th>Date</th>
                  <th className="ftable__num">Total</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((inv) => (
                  <tr key={inv.id} onClick={() => navigate(`/freelance/invoices/${inv.id}`)}>
                    <td className="tnum">{inv.number}</td>
                    <td>{inv.client_name ?? "—"}</td>
                    <td>{shortDate(inv.issue_date)}</td>
                    <td className="ftable__num tnum">{money(inv.total)}</td>
                    <td>
                      <span className={STATUS_CLASS[inv.status] ?? "badge"}>{inv.status}</span>
                      {inv.overdue && (
                        <span className="badge badge--recurring" style={{ marginLeft: 4 }}>überfällig</span>
                      )}
                      {inv.status !== "paid" && num(inv.paid_amount) > 0 && (
                        <span className="muted" style={{ fontSize: 11, marginLeft: 6 }}>
                          {money(inv.paid_amount)} erhalten
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          );
        }}
      </Async>

      {creating && (
        <Modal title="New invoice" className="modal--md" onClose={() => setCreating(false)}>
          <NewInvoiceForm onClose={() => setCreating(false)} />
        </Modal>
      )}
      </Card>
    </>
  );
}
