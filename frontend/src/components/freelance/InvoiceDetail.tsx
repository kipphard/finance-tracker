import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiDelete, apiDownload, apiPatch, apiPut } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import type { BusinessProfileOut, ClientOut, InvoiceOut } from "../../api/types";
import { money, num, shortDate } from "../../lib/format";
import { Card } from "../Card";
import { Async } from "../Async";
import { InvoiceEmailModal } from "./InvoiceEmailModal";
import {
  INTRO_DEFAULTS, INVOICE_STATUSES, LANGUAGES, isDefaultIntro, reminderStage, tidyDescription,
} from "./helpers";

interface Line {
  description: string;
  hours: string;
  rate: string;
  amount: string;
}

const round2 = (n: number) => (Number.isFinite(n) ? n : 0).toFixed(2);

function ItemsEditor({ invoice, onSaved }: { invoice: InvoiceOut; onSaved: () => void }) {
  const [lines, setLines] = useState<Line[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setLines(invoice.items.map((it) => ({
      description: it.description, hours: it.hours, rate: it.rate, amount: it.amount,
    })));
    setDirty(false);
  }, [invoice.id]);

  const mutate = (fn: (ls: Line[]) => Line[]) => { setLines(fn); setDirty(true); };
  // editing hours/rate recomputes the amount; editing amount directly makes it a flat line
  const setHours = (i: number, v: string) =>
    mutate((ls) => ls.map((l, x) => (x === i ? { ...l, hours: v, amount: round2(num(v) * num(l.rate)) } : l)));
  const setRate = (i: number, v: string) =>
    mutate((ls) => ls.map((l, x) => (x === i ? { ...l, rate: v, amount: round2(num(l.hours) * num(v)) } : l)));
  const setField = (i: number, patch: Partial<Line>) =>
    mutate((ls) => ls.map((l, x) => (x === i ? { ...l, ...patch } : l)));
  const addHourly = () =>
    mutate((ls) => [...ls, { description: "", hours: "0", rate: invoice.items[0]?.rate ?? "0", amount: "0" }]);
  const addFlat = () =>
    mutate((ls) => [...ls, { description: "", hours: "0", rate: "0", amount: "0" }]);
  const removeLine = (i: number) => mutate((ls) => ls.filter((_, x) => x !== i));

  // Rule-based "tidy": clean each description + merge duplicate lines (same desc & rate).
  const tidy = () => mutate((ls) => {
    const cleaned = ls.map((l) => ({ ...l, description: tidyDescription(l.description) }));
    const groups = new Map<string, Line & { _h: number; _a: number }>();
    const order: string[] = [];
    for (const l of cleaned) {
      const key = `${l.description.toLowerCase()}|${num(l.rate)}`;
      const g = groups.get(key);
      if (!g) { groups.set(key, { ...l, _h: num(l.hours), _a: num(l.amount) }); order.push(key); }
      else { g._h += num(l.hours); g._a += num(l.amount); }
    }
    return order.map((k) => {
      const g = groups.get(k)!;
      return { description: g.description, hours: round2(g._h), rate: g.rate, amount: round2(g._a) };
    });
  });

  const total = lines.reduce((sum, l) => sum + num(l.amount), 0);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await apiPut(`/invoices/${invoice.id}/items`, lines.map((l) => ({
        description: l.description,
        hours: l.hours || "0",
        rate: l.rate || "0",
        amount: l.amount || "0",
      })));
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="table-scroll">
      <table className="ftable inv-items">
        <thead>
          <tr>
            <th>Service</th>
            <th className="ftable__num">Hours</th>
            <th className="ftable__num">Rate</th>
            <th className="ftable__num">Amount</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {lines.map((l, i) => (
            <tr key={i}>
              <td>
                <input className="input" value={l.description} placeholder="Service / Pauschale"
                  onChange={(e) => setField(i, { description: e.target.value })} />
              </td>
              <td className="ftable__num">
                <input className="input inv-items__num" type="number" min="0" step="0.25" value={l.hours}
                  onChange={(e) => setHours(i, e.target.value)} />
              </td>
              <td className="ftable__num">
                <input className="input inv-items__num" type="number" min="0" step="0.01" value={l.rate}
                  onChange={(e) => setRate(i, e.target.value)} />
              </td>
              <td className="ftable__num">
                <input className="input inv-items__num" type="number" min="0" step="0.01" value={l.amount}
                  onChange={(e) => setField(i, { amount: e.target.value })} />
              </td>
              <td className="ftable__actions">
                <button className="btn btn--ghost btn--sm" style={{ padding: "2px 7px" }}
                  title="Remove line" onClick={() => removeLine(i)}>×</button>
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={3} className="inv-items__total-label">Invoice amount</td>
            <td className="ftable__num tnum inv-items__total">{money(total)}</td>
            <td></td>
          </tr>
        </tfoot>
      </table>
      </div>
      <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
        Hourly line: set Hours × Rate. Flat line: leave Hours at 0 and just type the Amount (shows no hours on the PDF).
      </div>
      {error && <div className="error">{error}</div>}
      <div className="toolbar" style={{ marginTop: 12 }}>
        <button className="btn btn--ghost btn--sm" onClick={addHourly}>+ Hourly line</button>
        <button className="btn btn--ghost btn--sm" onClick={addFlat}>+ Flat line</button>
        <button className="btn btn--ghost btn--sm" disabled={lines.length === 0} onClick={tidy}
          title="Clean up descriptions + merge duplicate lines">✨ Tidy</button>
        <button className="btn btn--sm" disabled={busy || !dirty} onClick={save}>
          {busy ? "…" : "Save lines"}
        </button>
      </div>
    </>
  );
}

function DetailsForm({ invoice, onSaved }: { invoice: InvoiceOut; onSaved: () => void }) {
  const [place, setPlace] = useState(invoice.place);
  const [issueDate, setIssueDate] = useState(invoice.issue_date);
  const [dueDate, setDueDate] = useState(invoice.due_date ?? "");
  const [status, setStatus] = useState(invoice.status);
  const [language, setLanguage] = useState<string>(invoice.language);
  const [intro, setIntro] = useState(invoice.intro_text);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setPlace(invoice.place);
    setIssueDate(invoice.issue_date);
    setDueDate(invoice.due_date ?? "");
    setStatus(invoice.status);
    setLanguage(invoice.language);
    // show the language's default intro when none is stored, so the field is never blank
    setIntro(invoice.intro_text || INTRO_DEFAULTS[invoice.language] || INTRO_DEFAULTS.de);
  }, [invoice.id]);

  // Switching the language re-translates the boilerplate intro — unless you've typed your own.
  const onLanguage = (next: string) => {
    setLanguage(next);
    if (isDefaultIntro(intro)) setIntro(INTRO_DEFAULTS[next] || "");
  };

  const save = async () => {
    setBusy(true);
    try {
      await apiPatch(`/invoices/${invoice.id}`, {
        place, issue_date: issueDate, due_date: dueDate || null, status, language, intro_text: intro,
      });
      onSaved();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="form">
      <div className="field-row">
        <div className="field">
          <label>Place</label>
          <input className="input" value={place} onChange={(e) => setPlace(e.target.value)}
            placeholder="City" />
        </div>
        <div className="field">
          <label>Issue date</label>
          <input className="input" type="date" value={issueDate} onChange={(e) => setIssueDate(e.target.value)} />
        </div>
        <div className="field">
          <label>Due date</label>
          <input className="input" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
        </div>
        <div className="field">
          <label>Language</label>
          <select className="select" value={language} onChange={(e) => onLanguage(e.target.value)}>
            {LANGUAGES.map((l) => (
              <option key={l.value} value={l.value}>{l.label}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Status</label>
          <select className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
            {INVOICE_STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="field">
        <label>Intro text</label>
        <textarea className="input" rows={3} value={intro} onChange={(e) => setIntro(e.target.value)} />
      </div>
      <div className="form__actions">
        <button className="btn btn--sm" disabled={busy} onClick={save}>{busy ? "…" : "Save details"}</button>
      </div>
    </div>
  );
}

export function InvoiceDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const state = useApi<InvoiceOut>(`/invoices/${id}`);
  const clients = useApi<ClientOut[]>("/clients");
  const profile = useApi<BusinessProfileOut>("/business-profile");
  const [emailing, setEmailing] = useState<{ inv: InvoiceOut; reminder: boolean } | null>(null);

  const download = async (inv: InvoiceOut) => {
    await apiDownload(`/invoices/${inv.id}/pdf`, `Rechnung${inv.number}.pdf`);
  };
  const remove = async (inv: InvoiceOut) => {
    if (!confirm(`Delete invoice ${inv.number}? Its time entries become unbilled again.`)) return;
    await apiDelete(`/invoices/${inv.id}`);
    navigate("/business/invoices");
  };

  return (
    <Async state={state}>
      {(inv) => (
        <>
          <button className="btn btn--ghost btn--sm" style={{ marginBottom: 12 }}
            onClick={() => navigate("/business/invoices")}>← All invoices</button>

          <Card
            title={`Invoice ${inv.number}`}
            action={
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button className="btn btn--sm" onClick={() => download(inv)}>⬇ PDF</button>
                <button className="btn btn--sm" onClick={() => setEmailing({ inv, reminder: false })}>✉ Email</button>
                {inv.status !== "paid" && (inv.status === "sent" || inv.overdue) && (
                  <button className="btn btn--sm" style={{ background: "var(--warn)", borderColor: "var(--warn)" }}
                    onClick={() => setEmailing({ inv, reminder: true })}>
                    ⏰ {reminderStage(inv.reminder_level + 1, inv.language)}
                  </button>
                )}
                <button className="btn btn--ghost btn--sm" onClick={() => remove(inv)}>Delete</button>
              </div>
            }
          >
            <div className="muted" style={{ marginBottom: 16 }}>
              {inv.client_name}
              {inv.project_name ? <> · {inv.project_name}</> : null} ·{" "}
              <span className="badge">{inv.status}</span>
              {inv.overdue && <span className="badge badge--recurring" style={{ marginLeft: 4 }}>überfällig</span>}
              {" · "}{inv.language.toUpperCase()}
              {inv.status !== "paid" && num(inv.paid_amount) > 0 && (
                <> · <span style={{ color: "var(--warn)" }}>
                  {money(inv.paid_amount)} von {money(inv.total)} erhalten
                </span></>
              )}
              {inv.reminder_level > 0 && (
                <> · <span style={{ color: "var(--warn)" }}>
                  {reminderStage(inv.reminder_level, inv.language)} gesendet
                  {inv.last_reminder_at ? ` am ${shortDate(inv.last_reminder_at)}` : ""}
                </span></>
              )}
            </div>
            <DetailsForm
              key={`${inv.status}|${inv.language}|${inv.issue_date}|${inv.due_date}|${inv.place}|${inv.intro_text}`}
              invoice={inv} onSaved={() => state.reload()} />
            <h3 style={{ margin: "22px 0 10px", fontSize: 15 }}>Line items</h3>
            <ItemsEditor invoice={inv} onSaved={() => state.reload()} />

            {inv.payments.length > 0 && (
              <div className="inv-payments">
                <h3 style={{ margin: "22px 0 8px", fontSize: 15 }}>Zahlungseingang</h3>
                <ul className="list">
                  {inv.payments.map((p) => (
                    <li key={p.id}>
                      <span>
                        <span className="li-main">{shortDate(p.ts)}</span>{" "}
                        <span className="li-sub">
                          {p.account_name ?? "—"}{p.payee ? ` · ${p.payee}` : ""}
                        </span>
                      </span>
                      <span className={"tnum " + (num(p.amount) >= 0 ? "pos" : "neg")}>
                        {money(p.amount)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>

          {emailing && (
            <InvoiceEmailModal
              invoice={emailing.inv}
              reminder={emailing.reminder}
              client={(clients.data ?? []).find((c) => c.id === emailing.inv.client_id)}
              profile={profile.data ?? undefined}
              onClose={() => setEmailing(null)}
              onSent={() => state.reload()}
            />
          )}
        </>
      )}
    </Async>
  );
}
