import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiPatch, apiPost } from "../api/client";
import type { AccountOut, CategoryOut, TransactionOut } from "../api/types";
import { money, num, shortDate } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";
import { Modal } from "./Modal";
import { AttachmentsModal } from "./AttachmentsModal";

// First future occurrence for a recurring template (the one logged now covers "today").
function nextDue(cadence: string): string {
  const d = new Date();
  if (cadence === "weekly") d.setDate(d.getDate() + 7);
  else if (cadence === "biweekly") d.setDate(d.getDate() + 14);
  else if (cadence === "monthly") d.setMonth(d.getMonth() + 1);
  else if (cadence === "quarterly") d.setMonth(d.getMonth() + 3);
  else if (cadence === "yearly") d.setFullYear(d.getFullYear() + 1);
  return d.toISOString().slice(0, 10);
}

function TransactionForm({
  accounts,
  onSubmit,
  onClose,
}: {
  accounts: AccountOut[];
  onSubmit: (
    account: { accountId: string | null; newAccountName: string | null },
    body: any,
    repeat: string,
  ) => Promise<void>;
  onClose: () => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const hasAccounts = accounts.length > 0;
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? "");
  const [newAccountName, setNewAccountName] = useState("Main");
  const [date, setDate] = useState(today);
  const [amount, setAmount] = useState("");
  const [payee, setPayee] = useState("");
  const [counterparty, setCounterparty] = useState("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [vatRate, setVatRate] = useState("");
  const [description, setDescription] = useState("");
  const [showDetails, setShowDetails] = useState(false);
  const [repeat, setRepeat] = useState("none");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit(
        {
          accountId: hasAccounts ? accountId : null,
          newAccountName: hasAccounts ? null : newAccountName.trim() || "Main",
        },
        {
          ts: `${date}T00:00:00Z`,
          amount,
          raw_payee: payee || null,
          description: description || null,
          counterparty: counterparty || null,
          invoice_number: invoiceNumber || null,
          vat_rate: vatRate || null,
        },
        repeat,
      );
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="form" onSubmit={submit}>
      <div className="field-row">
        <div className="field">
          <label>Account</label>
          {hasAccounts ? (
            <select className="select" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
              {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          ) : (
            <input className="input" placeholder="Account name (e.g. Main)" value={newAccountName}
              onChange={(e) => setNewAccountName(e.target.value)} />
          )}
        </div>
        <div className="field">
          <label>Date</label>
          <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
      </div>
      <div className="field">
        <label>Amount (negative = spending)</label>
        <input className="input" type="number" step="0.01" placeholder="-12.34" value={amount}
          onChange={(e) => setAmount(e.target.value)} required autoFocus />
      </div>
      <div className="field-row">
        <div className="field">
          <label>Payee</label>
          <input className="input" placeholder="e.g. REWE" value={payee} onChange={(e) => setPayee(e.target.value)} />
        </div>
        <div className="field">
          <label>Repeat</label>
          <select className="select" value={repeat} onChange={(e) => setRepeat(e.target.value)}>
            <option value="none">No — one-off</option>
            <option value="weekly">Weekly</option>
            <option value="biweekly">Every 2 weeks</option>
            <option value="monthly">Monthly</option>
            <option value="quarterly">Quarterly</option>
            <option value="yearly">Yearly</option>
          </select>
        </div>
      </div>
      {showDetails ? (
        <>
          <div className="field">
            <label>Counterparty / client (optional)</label>
            <input className="input" placeholder="e.g. ACME GmbH" value={counterparty} onChange={(e) => setCounterparty(e.target.value)} />
          </div>
          <div className="field-row">
            <div className="field">
              <label>Invoice no. (optional)</label>
              <input className="input" placeholder="e.g. 2026-014" value={invoiceNumber} onChange={(e) => setInvoiceNumber(e.target.value)} />
            </div>
            <div className="field">
              <label>VAT % (optional)</label>
              <input className="input" type="number" step="0.1" placeholder="19" value={vatRate} onChange={(e) => setVatRate(e.target.value)} />
            </div>
          </div>
        </>
      ) : (
        <button type="button" className="btn btn--ghost btn--sm" style={{ alignSelf: "flex-start" }}
          onClick={() => setShowDetails(true)}>
          + Invoice / client details (optional)
        </button>
      )}
      <div className="field">
        <label>Note (optional)</label>
        <input className="input" value={description} onChange={(e) => setDescription(e.target.value)} />
      </div>
      {error && <div className="error">{error}</div>}
      <div className="form__actions">
        <button type="button" className="btn btn--ghost" onClick={onClose}>Cancel</button>
        <button className="btn" type="submit" disabled={busy}>{busy ? "…" : "Add transaction"}</button>
      </div>
    </form>
  );
}

export function TransactionsTable({ className }: { className?: string }) {
  const txns = useApi<TransactionOut[]>("/transactions");
  const cats = useApi<CategoryOut[]>("/categories");
  const accounts = useApi<AccountOut[]>("/accounts");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [adding, setAdding] = useState(false);
  const [attachFor, setAttachFor] = useState<string | null>(null);

  const recategorize = async (id: string, categoryId: string) => {
    await apiPatch(`/transactions/${id}`, { category_id: categoryId || null });
    txns.reload();
  };
  const addTxn = async (
    account: { accountId: string | null; newAccountName: string | null },
    body: any,
    repeat: string,
  ) => {
    let accountId = account.accountId;
    if (!accountId) {
      const created = await apiPost<AccountOut>("/accounts", {
        type: "cash",
        name: account.newAccountName || "Main",
        currency: "EUR",
      });
      accountId = created.id;
      accounts.reload();
    }
    await apiPost(`/accounts/${accountId}/transactions`, body);
    if (repeat && repeat !== "none") {
      const amt = parseFloat(body.amount);
      await apiPost("/cashflow", {
        direction: amt >= 0 ? "inflow" : "outflow",
        name: body.raw_payee || "Recurring",
        amount: String(Math.abs(amt) || 0.01),
        cadence: repeat,
        account_id: accountId,
        next_due: nextDue(repeat),
      });
    }
    txns.reload();
  };

  const action = (
    <button className="btn btn--sm" onClick={() => setAdding(true)}>
      + Transaction
    </button>
  );

  return (
    <Card title="Transactions" className={className} action={action}>
      <div className="toolbar">
        <input className="input" placeholder="Search payee / description…" value={query}
          onChange={(e) => setQuery(e.target.value)} style={{ flex: 1, minWidth: 180 }} />
        <select className="select" value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">All categories</option>
          <option value="uncategorized">Uncategorized</option>
          {cats.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>

      <Async state={txns}>
        {(list) => {
          let rows = list;
          if (filter === "uncategorized") rows = rows.filter((t) => !t.category_id);
          else if (filter !== "all") rows = rows.filter((t) => t.category_id === filter);
          const q = query.trim().toLowerCase();
          if (q)
            rows = rows.filter(
              (t) =>
                (t.raw_payee || "").toLowerCase().includes(q) ||
                (t.description || "").toLowerCase().includes(q),
            );
          if (rows.length === 0)
            return <div className="empty">No transactions yet — add one or import a CSV.</div>;
          return (
            <div style={{ overflowX: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Payee</th>
                    <th className="amount">Amount</th>
                    <th>Category</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((t) => (
                    <tr key={t.id}>
                      <td>{shortDate(t.ts)}</td>
                      <td>
                        <div>
                          {t.raw_payee || "—"}{" "}
                          {t.is_recurring && <span className="badge badge--recurring">recurring</span>}
                        </div>
                        {(t.counterparty || t.invoice_number) && (
                          <div className="li-sub">
                            {t.counterparty}
                            {t.counterparty && t.invoice_number ? " · " : ""}
                            {t.invoice_number ? `#${t.invoice_number}` : ""}
                          </div>
                        )}
                      </td>
                      <td className={"amount " + (num(t.amount) >= 0 ? "pos" : "neg")}>
                        {money(t.amount, t.currency)}
                      </td>
                      <td>
                        <select className="select" value={t.category_id || ""}
                          onChange={(e) => recategorize(t.id, e.target.value)}>
                          <option value="">— none —</option>
                          {cats.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                        </select>
                      </td>
                      <td className="amount">
                        <button className="btn btn--ghost btn--sm" style={{ padding: "2px 8px" }}
                          onClick={() => setAttachFor(t.id)} title="Attachments (invoice/receipt)">
                          📎
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }}
      </Async>

      {adding && (
        <Modal title="Add transaction" onClose={() => setAdding(false)}>
          <TransactionForm
            accounts={accounts.data ?? []}
            onClose={() => setAdding(false)}
            onSubmit={addTxn}
          />
        </Modal>
      )}
      {attachFor && (
        <AttachmentsModal txnId={attachFor} onClose={() => setAttachFor(null)} />
      )}
    </Card>
  );
}
