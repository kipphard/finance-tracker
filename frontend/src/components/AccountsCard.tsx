import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiDelete, apiPatch, apiPost } from "../api/client";
import type { AccountOut } from "../api/types";
import { money, titleCase } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";
import { Modal } from "./Modal";

const TYPES = ["checking", "savings", "cash", "brokerage", "other"];

function AccountForm({
  initial,
  onSubmit,
  onDelete,
  onClose,
}: {
  initial?: AccountOut;
  onSubmit: (v: any) => Promise<void>;
  onDelete?: () => Promise<void>;
  onClose: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [type, setType] = useState(initial?.type ?? "checking");
  const [currency, setCurrency] = useState(initial?.currency ?? "EUR");
  const [opening, setOpening] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const editing = !!initial;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit({ name, type, currency, opening });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!onDelete) return;
    if (!window.confirm("Delete this account and all its transactions?")) return;
    setBusy(true);
    try {
      await onDelete();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
      setBusy(false);
    }
  };

  return (
    <form className="form" onSubmit={submit}>
      <div className="field">
        <label>Name</label>
        <input className="input" placeholder="e.g. Giro, Wallet, Broker" value={name}
          onChange={(e) => setName(e.target.value)} required autoFocus />
      </div>
      <div className="field-row">
        <div className="field">
          <label>Type</label>
          <select className="select" value={type} onChange={(e) => setType(e.target.value)}>
            {TYPES.map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Currency</label>
          <input className="input" value={currency} maxLength={3}
            onChange={(e) => setCurrency(e.target.value.toUpperCase())} />
        </div>
      </div>
      {!editing && (
        <div className="field">
          <label>Starting balance (optional)</label>
          <input className="input" type="number" step="0.01" placeholder="0.00" value={opening}
            onChange={(e) => setOpening(e.target.value)} />
        </div>
      )}
      {error && <div className="error">{error}</div>}
      <div className="form__actions" style={editing ? { justifyContent: "space-between" } : undefined}>
        {editing && onDelete && (
          <button type="button" className="btn btn--ghost" onClick={remove} disabled={busy}
            style={{ borderColor: "var(--negative)", color: "var(--negative)" }}>
            Delete
          </button>
        )}
        <span style={{ display: "flex", gap: 10 }}>
          <button type="button" className="btn btn--ghost" onClick={onClose}>Cancel</button>
          <button className="btn" type="submit" disabled={busy}>{busy ? "…" : editing ? "Save" : "Add account"}</button>
        </span>
      </div>
    </form>
  );
}

export function AccountsCard({ className }: { className?: string }) {
  const state = useApi<AccountOut[]>("/accounts");
  const [modal, setModal] = useState<{ edit?: AccountOut } | null>(null);

  const create = async (v: any) => {
    const acc = await apiPost<AccountOut>("/accounts", { name: v.name, type: v.type, currency: v.currency });
    if (v.opening && parseFloat(v.opening) !== 0) {
      await apiPost(`/accounts/${acc.id}/transactions`, {
        ts: new Date().toISOString().slice(0, 10) + "T00:00:00Z",
        amount: v.opening,
        raw_payee: "Opening balance",
      });
    }
    state.reload();
  };
  const edit = async (id: string, v: any) => {
    await apiPatch(`/accounts/${id}`, { name: v.name, type: v.type, currency: v.currency });
    state.reload();
  };
  const remove = async (id: string) => {
    await apiDelete(`/accounts/${id}`);
    state.reload();
  };

  const action = (
    <button className="btn btn--sm" onClick={() => setModal({})}>+ Account</button>
  );

  return (
    <Card title="Accounts" className={className} action={action}>
      <Async state={state}>
        {(accounts) =>
          accounts.length === 0 ? (
            <div className="empty">No accounts yet — add one to start tracking.</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th className="amount">Balance</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {[...accounts].sort((a, b) => a.name.localeCompare(b.name)).map((a) => (
                  <tr key={a.id}>
                    <td>{a.name}</td>
                    <td>{titleCase(a.type)}</td>
                    <td className="amount">
                      {a.latest_balance != null ? money(a.latest_balance, a.currency) : money(0, a.currency)}
                    </td>
                    <td className="amount">
                      <button className="btn btn--ghost btn--sm" style={{ padding: "2px 8px" }}
                        onClick={() => setModal({ edit: a })} title="Edit account">
                        ✎
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        }
      </Async>

      {modal && (
        <Modal title={modal.edit ? "Edit account" : "Add account"} onClose={() => setModal(null)}>
          <AccountForm
            initial={modal.edit}
            onClose={() => setModal(null)}
            onSubmit={(v) => (modal.edit ? edit(modal.edit.id, v) : create(v))}
            onDelete={modal.edit ? () => remove(modal.edit!.id) : undefined}
          />
        </Modal>
      )}
    </Card>
  );
}
