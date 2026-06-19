import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiDelete, apiPatch, apiPost } from "../api/client";
import type { DebtOut } from "../api/types";
import { money, num, shortDate } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";
import { Modal } from "./Modal";

function DebtForm({ onSubmit, onClose }: { onSubmit: (v: any) => Promise<void>; onClose: () => void }) {
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit({ name, amount, due_date: dueDate || null });
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
        <label>What needs paying?</label>
        <input className="input" placeholder="e.g. Car repair" value={name}
          onChange={(e) => setName(e.target.value)} required autoFocus />
      </div>
      <div className="field-row">
        <div className="field">
          <label>Amount (€)</label>
          <input className="input" type="number" min="0.01" step="0.01" placeholder="0.00"
            value={amount} onChange={(e) => setAmount(e.target.value)} required />
        </div>
        <div className="field">
          <label>Due date (optional)</label>
          <input className="input" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
        </div>
      </div>
      {error && <div className="error">{error}</div>}
      <div className="form__actions">
        <button type="button" className="btn btn--ghost" onClick={onClose}>Cancel</button>
        <button className="btn" type="submit" disabled={busy}>{busy ? "…" : "Add"}</button>
      </div>
    </form>
  );
}

export function DebtsCard({ className }: { className?: string }) {
  const state = useApi<DebtOut[]>("/debts");
  const [open, setOpen] = useState(false);
  const [showPaid, setShowPaid] = useState(false);
  const today = new Date().toISOString().slice(0, 10);

  const add = async (v: any) => {
    await apiPost("/debts", v);
    state.reload();
  };
  const setPaid = async (id: string, paid: boolean) => {
    await apiPatch(`/debts/${id}`, { paid });
    state.reload();
  };
  const remove = async (id: string) => {
    await apiDelete(`/debts/${id}`);
    state.reload();
  };

  const action = (
    <button className="btn btn--sm" onClick={() => setOpen(true)}>
      + Add
    </button>
  );

  return (
    <Card title="To pay off" className={className} action={action}>
      <Async state={state}>
        {(debts) => {
          const unpaid = debts.filter((d) => !d.paid);
          const paid = debts.filter((d) => d.paid);
          const outstanding = unpaid.reduce((sum, d) => sum + num(d.amount), 0);

          return (
            <>
              <div className="metric-row">
                <div className="metric-block">
                  <div className="label">Outstanding</div>
                  <div className={"value " + (outstanding > 0 ? "neg" : "")}>
                    {money(outstanding)}
                  </div>
                </div>
              </div>

              {unpaid.length === 0 ? (
                <div className="empty">Nothing to pay off. 🎉</div>
              ) : (
                <ul className="list">
                  {unpaid.map((d) => {
                    const overdue = d.due_date != null && d.due_date < today;
                    return (
                      <li key={d.id}>
                        <span>
                          <span className="li-main">{d.name}</span>{" "}
                          {d.due_date && (
                            <span className={"li-sub " + (overdue ? "neg" : "")}>
                              · {overdue ? "overdue " : "due "}
                              {shortDate(d.due_date)}
                            </span>
                          )}
                        </span>
                        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span className="tnum neg">{money(d.amount)}</span>
                          <button className="btn btn--ghost btn--sm" onClick={() => setPaid(d.id, true)}>
                            Paid
                          </button>
                          <button className="btn btn--ghost btn--sm" style={{ padding: "2px 7px" }}
                            onClick={() => remove(d.id)} title="Delete">
                            ×
                          </button>
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}

              {paid.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <button className="btn btn--ghost btn--sm" onClick={() => setShowPaid((s) => !s)}>
                    {showPaid ? "Hide" : "Show"} paid ({paid.length})
                  </button>
                  {showPaid && (
                    <ul className="list" style={{ marginTop: 8 }}>
                      {paid.map((d) => (
                        <li key={d.id}>
                          <span className="muted" style={{ textDecoration: "line-through" }}>
                            {d.name} · {money(d.amount)}
                          </span>
                          <span style={{ display: "flex", gap: 8 }}>
                            <button className="btn btn--ghost btn--sm" onClick={() => setPaid(d.id, false)}>
                              Undo
                            </button>
                            <button className="btn btn--ghost btn--sm" style={{ padding: "2px 7px" }}
                              onClick={() => remove(d.id)} title="Delete">
                              ×
                            </button>
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </>
          );
        }}
      </Async>

      {open && (
        <Modal title="Add something to pay off" onClose={() => setOpen(false)}>
          <DebtForm onClose={() => setOpen(false)} onSubmit={add} />
        </Modal>
      )}
    </Card>
  );
}
