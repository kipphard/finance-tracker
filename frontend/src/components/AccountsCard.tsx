import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiPost } from "../api/client";
import type { AccountOut } from "../api/types";
import { money, titleCase } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";
import { Modal } from "./Modal";

const TYPES = ["checking", "savings", "cash", "brokerage", "other"];

function AccountForm({ onSubmit, onClose }: { onSubmit: (v: any) => Promise<void>; onClose: () => void }) {
  const [name, setName] = useState("");
  const [type, setType] = useState("checking");
  const [currency, setCurrency] = useState("EUR");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit({ name, type, currency });
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
      {error && <div className="error">{error}</div>}
      <div className="form__actions">
        <button type="button" className="btn btn--ghost" onClick={onClose}>Cancel</button>
        <button className="btn" type="submit" disabled={busy}>{busy ? "…" : "Add account"}</button>
      </div>
    </form>
  );
}

function BalanceForm({ onSubmit, onClose }: { onSubmit: (amount: string) => Promise<void>; onClose: () => void }) {
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit(amount);
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
        <label>Current balance</label>
        <input className="input" type="number" step="0.01" placeholder="0.00" value={amount}
          onChange={(e) => setAmount(e.target.value)} required autoFocus />
      </div>
      {error && <div className="error">{error}</div>}
      <div className="form__actions">
        <button type="button" className="btn btn--ghost" onClick={onClose}>Cancel</button>
        <button className="btn" type="submit" disabled={busy}>{busy ? "…" : "Save balance"}</button>
      </div>
    </form>
  );
}

export function AccountsCard({ className }: { className?: string }) {
  const state = useApi<AccountOut[]>("/accounts");
  const [modal, setModal] = useState<
    { kind: "account" } | { kind: "balance"; id: string; name: string } | null
  >(null);

  const addAccount = async (v: { name: string; type: string; currency: string }) => {
    await apiPost("/accounts", v);
    state.reload();
  };
  const addBalance = async (id: string, amount: string) => {
    await apiPost(`/accounts/${id}/balances`, { amount });
    state.reload();
  };

  const action = (
    <button className="btn btn--sm" onClick={() => setModal({ kind: "account" })}>
      + Account
    </button>
  );

  return (
    <Card title="Accounts" className={className} action={action}>
      <Async state={state}>
        {(accounts) =>
          accounts.length === 0 ? (
            <div className="empty">No accounts yet — add one to track your balance.</div>
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
                {accounts.map((a) => (
                  <tr key={a.id}>
                    <td>{a.name}</td>
                    <td>{titleCase(a.type)}</td>
                    <td className="amount">
                      {a.latest_balance != null ? money(a.latest_balance, a.currency) : "—"}
                    </td>
                    <td className="amount">
                      <button
                        className="btn btn--ghost btn--sm"
                        onClick={() => setModal({ kind: "balance", id: a.id, name: a.name })}
                        title="Update balance"
                      >
                        + €
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        }
      </Async>

      {modal?.kind === "account" && (
        <Modal title="Add account" onClose={() => setModal(null)}>
          <AccountForm onClose={() => setModal(null)} onSubmit={addAccount} />
        </Modal>
      )}
      {modal?.kind === "balance" && (
        <Modal title={`Update balance — ${modal.name}`} onClose={() => setModal(null)}>
          <BalanceForm
            onClose={() => setModal(null)}
            onSubmit={(amount) => addBalance(modal.id, amount)}
          />
        </Modal>
      )}
    </Card>
  );
}
