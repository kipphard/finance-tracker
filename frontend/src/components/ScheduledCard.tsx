import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiDelete, apiPatch } from "../api/client";
import type { Cadence, CashflowItemOut } from "../api/types";
import { money, shortDate, titleCase } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";
import { Modal } from "./Modal";
import { Pager, paginate, usePageSize } from "./Pager";

const CADENCES: Cadence[] = ["weekly", "biweekly", "monthly", "quarterly", "yearly"];

function ScheduledEditForm({
  item,
  onClose,
  onSaved,
}: {
  item: CashflowItemOut;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(item.name);
  const [amount, setAmount] = useState(item.amount);
  const [cadence, setCadence] = useState<Cadence>(item.cadence);
  const [nextDue, setNextDue] = useState(item.next_due ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiPatch(`/cashflow/${item.id}`, {
        name,
        amount,
        cadence,
        next_due: nextDue || null,
      });
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
      setBusy(false);
    }
  };

  return (
    <form className="form" onSubmit={save}>
      <div className="field">
        <label>Name</label>
        <input className="input" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
      </div>
      <div className="field-row">
        <div className="field">
          <label>Amount</label>
          <input className="input" type="number" step="0.01" min="0" value={amount}
            onChange={(e) => setAmount(e.target.value)} required />
        </div>
        <div className="field">
          <label>Repeat every</label>
          <select className="select" value={cadence} onChange={(e) => setCadence(e.target.value as Cadence)}>
            {CADENCES.map((c) => <option key={c} value={c}>{titleCase(c)}</option>)}
          </select>
        </div>
      </div>
      <div className="field">
        <label>Next date {item.account_id ? "" : "(no account — won't auto-post)"}</label>
        <input className="input" type="date" value={nextDue} onChange={(e) => setNextDue(e.target.value)} />
      </div>
      {error && <div className="error">{error}</div>}
      <div className="form__actions">
        <button type="button" className="btn btn--ghost" onClick={onClose}>Cancel</button>
        <button className="btn" type="submit" disabled={busy}>{busy ? "…" : "Save"}</button>
      </div>
    </form>
  );
}

export function ScheduledCard({ className }: { className?: string }) {
  const state = useApi<CashflowItemOut[]>("/cashflow");
  const [editing, setEditing] = useState<CashflowItemOut | null>(null);
  const [page, setPage] = useState(0);
  const size = usePageSize();

  const stop = async (id: string) => {
    await apiDelete(`/cashflow/${id}`);
    state.reload();
  };

  return (
    <Card title="Scheduled (auto-repeats)" className={className}>
      <Async state={state}>
        {(items) => {
          // All active recurring items. Those with a target account auto-post transactions;
          // those without still count toward the monthly plan (income / fixed costs), so we
          // show them here too — otherwise they'd silently skew the numbers while staying hidden.
          const templates = items.filter((i) => i.active && i.cadence !== "one_off");
          if (templates.length === 0)
            return (
              <div className="empty">
                Nothing scheduled. Tick "Repeat" when adding a transaction and it'll post
                automatically.
              </div>
            );
          const { pages, page: p, slice } = paginate(templates, page, size);
          return (
            <>
            <ul className="list">
              {slice.map((t) => (
                <li key={t.id}>
                  <span>
                    <span className="li-main">{t.name}</span>{" "}
                    <span className="li-sub">
                      · {titleCase(t.cadence)} ·{" "}
                      {t.account_id ? `next ${shortDate(t.next_due)}` : "budget only"}
                    </span>
                  </span>
                  <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span className={"tnum " + (t.direction === "inflow" ? "pos" : "neg")}>
                      {t.direction === "inflow" ? "+" : "−"}
                      {money(t.amount, t.currency)}
                    </span>
                    <button className="btn btn--ghost btn--sm" style={{ padding: "2px 7px" }}
                      onClick={() => setEditing(t)} title="Edit schedule">
                      ✎
                    </button>
                    <button className="btn btn--ghost btn--sm" style={{ padding: "2px 7px" }}
                      onClick={() => stop(t.id)} title="Stop repeating">
                      ×
                    </button>
                  </span>
                </li>
              ))}
            </ul>
            <Pager page={p} pages={pages} total={templates.length} onPage={setPage} />
            </>
          );
        }}
      </Async>

      {editing && (
        <Modal title="Edit schedule" onClose={() => setEditing(null)}>
          <ScheduledEditForm item={editing} onClose={() => setEditing(null)} onSaved={() => state.reload()} />
        </Modal>
      )}
    </Card>
  );
}
