import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiDelete, apiPatch, apiPost } from "../api/client";
import type { AccountOut } from "../api/types";
import { money, num, titleCase } from "../lib/format";
import { useManualOrder } from "../hooks/useManualOrder";
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
  const [balance, setBalance] = useState(initial ? String(num(initial.latest_balance ?? 0)) : "");
  const [expectedReturn, setExpectedReturn] = useState(
    initial ? String(num(initial.expected_return)) : "",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const editing = !!initial;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit({ name, type, currency, opening, balance, expectedReturn });
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
      <div className="field">
        <label>Expected annual return % (optional)</label>
        <input className="input" type="number" step="0.1" placeholder="0" value={expectedReturn}
          onChange={(e) => setExpectedReturn(e.target.value)} />
        <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
          Feeds the net-worth forecast — e.g. 7 for a stock account, 0 for cash.
        </div>
      </div>
      {!editing && (
        <div className="field">
          <label>Starting balance (optional)</label>
          <input className="input" type="number" step="0.01" placeholder="0.00" value={opening}
            onChange={(e) => setOpening(e.target.value)} />
        </div>
      )}
      {editing && (
        <div className="field">
          <label>Balance</label>
          <input className="input" type="number" step="0.01" value={balance}
            onChange={(e) => setBalance(e.target.value)} />
          <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
            Changing this books a balance-adjustment transaction so your history stays correct.
          </div>
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

function TransferForm({
  accounts,
  onSubmit,
  onClose,
}: {
  accounts: AccountOut[];
  onSubmit: (v: any) => Promise<void>;
  onClose: () => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [from, setFrom] = useState(accounts[0]?.id ?? "");
  const [to, setTo] = useState(accounts.find((a) => a.id !== accounts[0]?.id)?.id ?? "");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(today);
  const [note, setNote] = useState("");
  const [tags, setTags] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (from === to) {
      setError("Pick two different accounts");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onSubmit({
        from_account_id: from,
        to_account_id: to,
        amount,
        ts: `${date}T00:00:00Z`,
        note: note || null,
        tags: tags.split(",").map((s) => s.trim()).filter(Boolean),
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
      setBusy(false);
    }
  };

  return (
    <form className="form" onSubmit={submit}>
      <div className="field-row">
        <div className="field">
          <label>From</label>
          <select className="select" value={from} onChange={(e) => setFrom(e.target.value)}>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label>To</label>
          <select className="select" value={to} onChange={(e) => setTo(e.target.value)}>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </div>
      </div>
      <div className="field-row">
        <div className="field">
          <label>Amount</label>
          <input className="input" type="number" step="0.01" min="0" placeholder="1000.00"
            value={amount} onChange={(e) => setAmount(e.target.value)} required autoFocus />
        </div>
        <div className="field">
          <label>Date</label>
          <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
      </div>
      <div className="field">
        <label>Note (optional)</label>
        <input className="input" placeholder="e.g. move savings to broker" value={note}
          onChange={(e) => setNote(e.target.value)} />
      </div>
      <div className="field">
        <label>Tags (optional)</label>
        <input className="input" placeholder="e.g. investment" value={tags}
          onChange={(e) => setTags(e.target.value)} />
      </div>
      {error && <div className="error">{error}</div>}
      <div className="form__actions">
        <button type="button" className="btn btn--ghost" onClick={onClose}>Cancel</button>
        <button className="btn" type="submit" disabled={busy || !amount || from === to}>
          {busy ? "…" : "Transfer"}
        </button>
      </div>
    </form>
  );
}

export function AccountsCard({ className }: { className?: string }) {
  const state = useApi<AccountOut[]>("/accounts");
  const [modal, setModal] = useState<{ edit?: AccountOut } | null>(null);
  const [transferOpen, setTransferOpen] = useState(false);
  const dnd = useManualOrder("ft_order_accounts");
  const accountList = state.data ?? [];

  const create = async (v: any) => {
    const acc = await apiPost<AccountOut>("/accounts", {
      name: v.name,
      type: v.type,
      currency: v.currency,
      expected_return: v.expectedReturn || "0",
    });
    if (v.opening && parseFloat(v.opening) !== 0) {
      await apiPost(`/accounts/${acc.id}/transactions`, {
        ts: new Date().toISOString().slice(0, 10) + "T00:00:00Z",
        amount: v.opening,
        raw_payee: "Opening balance",
      });
    }
    state.reload();
  };
  const edit = async (account: AccountOut, v: any) => {
    await apiPatch(`/accounts/${account.id}`, {
      name: v.name,
      type: v.type,
      currency: v.currency,
      expected_return: v.expectedReturn || "0",
    });
    const target = parseFloat(v.balance);
    if (v.balance !== "" && !Number.isNaN(target)) {
      const current = num(account.latest_balance ?? 0);
      const delta = Math.round((target - current) * 100) / 100;
      if (Math.abs(delta) >= 0.005) {
        await apiPost(`/accounts/${account.id}/transactions`, {
          ts: new Date().toISOString().slice(0, 10) + "T00:00:00Z",
          amount: delta.toFixed(2),
          raw_payee: "Balance adjustment",
        });
      }
    }
    state.reload();
  };
  const remove = async (id: string) => {
    await apiDelete(`/accounts/${id}`);
    state.reload();
  };
  const transfer = async (v: any) => {
    await apiPost("/transfers", v);
    state.reload();
  };

  const action = (
    <span style={{ display: "flex", gap: 8 }}>
      {accountList.length >= 2 && (
        <button className="btn btn--ghost btn--sm" onClick={() => setTransferOpen(true)}>
          ⇄ Transfer
        </button>
      )}
      <button className="btn btn--sm" onClick={() => setModal({})}>+ Account</button>
    </span>
  );

  return (
    <Card title="Accounts" className={className} action={action}>
      <Async state={state}>
        {(accounts) =>
          accounts.length === 0 ? (
            <div className="empty">No accounts yet — add one to start tracking.</div>
          ) : (
            (() => {
              const byName = [...accounts].sort((a, b) => a.name.localeCompare(b.name));
              const eff = dnd.reconcile(byName.map((a) => a.id));
              const ordered = [...accounts].sort((a, b) => eff.indexOf(a.id) - eff.indexOf(b.id));
              return (
                <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th className="grip-cell"></th>
                      <th>Name</th>
                      <th>Type</th>
                      <th className="amount">Balance</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {ordered.map((a) => (
                      <tr
                        key={a.id}
                        className={dnd.dragging === a.id ? "is-dragging" : ""}
                        onDragOver={(e) => e.preventDefault()}
                        onDragEnter={() => dnd.over(a.id)}
                        onDrop={(e) => {
                          e.preventDefault();
                          dnd.end();
                        }}
                      >
                        <td className="grip-cell">
                          <span
                            className="row-grip"
                            draggable
                            title="Drag to reorder"
                            onDragStart={(e) => {
                              dnd.start(a.id);
                              e.dataTransfer.effectAllowed = "move";
                              const tr = (e.currentTarget as HTMLElement).closest("tr");
                              if (tr) e.dataTransfer.setDragImage(tr, 16, 16);
                            }}
                            onDragEnd={dnd.end}
                          >
                            ⠿
                          </span>
                        </td>
                        <td>{a.name}</td>
                        <td>
                          {titleCase(a.type)}
                          {num(a.expected_return) !== 0 && (
                            <span className="muted"> · {num(a.expected_return)}%/yr</span>
                          )}
                        </td>
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
                </div>
              );
            })()
          )
        }
      </Async>

      {modal && (
        <Modal title={modal.edit ? "Edit account" : "Add account"} onClose={() => setModal(null)}>
          <AccountForm
            initial={modal.edit}
            onClose={() => setModal(null)}
            onSubmit={(v) => (modal.edit ? edit(modal.edit, v) : create(v))}
            onDelete={modal.edit ? () => remove(modal.edit!.id) : undefined}
          />
        </Modal>
      )}

      {transferOpen && (
        <Modal title="Transfer between accounts" onClose={() => setTransferOpen(false)}>
          <TransferForm
            accounts={accountList}
            onClose={() => setTransferOpen(false)}
            onSubmit={transfer}
          />
        </Modal>
      )}
    </Card>
  );
}
