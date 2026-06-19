import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useApi } from "../hooks/useApi";
import { useTheme } from "../theme";
import { apiDelete, apiPatch, apiPost } from "../api/client";
import type { AccountOut, Cadence, CashflowItemOut, CashflowSummaryOut } from "../api/types";
import { money, num, titleCase } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";
import { Modal } from "./Modal";

const CADENCES: Cadence[] = ["monthly", "weekly", "biweekly", "quarterly", "yearly", "one_off"];

interface FormValues {
  name: string;
  amount: string;
  cadence: Cadence;
  account_id: string | null;
}

function CashflowForm({
  initial,
  accounts,
  onSubmit,
  onClose,
}: {
  initial?: CashflowItemOut;
  accounts: AccountOut[];
  onSubmit: (v: FormValues) => Promise<void>;
  onClose: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [amount, setAmount] = useState(initial?.amount ?? "");
  const [cadence, setCadence] = useState<Cadence>(initial?.cadence ?? "monthly");
  const [accountId, setAccountId] = useState(initial?.account_id ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit({ name, amount, cadence, account_id: accountId || null });
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
        <label>Purpose</label>
        <input className="input" placeholder="e.g. Salary, Rent, Netflix" value={name}
          onChange={(e) => setName(e.target.value)} required autoFocus />
      </div>
      <div className="field-row">
        <div className="field">
          <label>Amount (€)</label>
          <input className="input" type="number" min="0.01" step="0.01" placeholder="0.00"
            value={amount} onChange={(e) => setAmount(e.target.value)} required />
        </div>
        <div className="field">
          <label>Frequency</label>
          <select className="select" value={cadence} onChange={(e) => setCadence(e.target.value as Cadence)}>
            {CADENCES.map((c) => <option key={c} value={c}>{titleCase(c)}</option>)}
          </select>
        </div>
      </div>
      <div className="field">
        <label>Post to account (optional — enables "Post" to the ledger)</label>
        <select className="select" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
          <option value="">— none —</option>
          {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </div>
      {error && <div className="error">{error}</div>}
      <div className="form__actions">
        <button type="button" className="btn btn--ghost" onClick={onClose}>Cancel</button>
        <button className="btn" type="submit" disabled={busy}>{busy ? "…" : "Save"}</button>
      </div>
    </form>
  );
}

export function CashflowCard({ className }: { className?: string }) {
  const summary = useApi<CashflowSummaryOut>("/cashflow/summary");
  const items = useApi<CashflowItemOut[]>("/cashflow");
  const accounts = useApi<AccountOut[]>("/accounts");
  const { grid, axis } = useTheme();
  const [modal, setModal] = useState<{ direction: "inflow" | "outflow"; item?: CashflowItemOut } | null>(null);
  const [posting, setPosting] = useState(false);
  const [posted, setPosted] = useState<string | null>(null);

  const reload = () => {
    summary.reload();
    items.reload();
  };

  const submit = async (values: FormValues) => {
    if (modal?.item) {
      await apiPatch(`/cashflow/${modal.item.id}`, {
        name: values.name, amount: values.amount, cadence: values.cadence, account_id: values.account_id,
      });
    } else {
      await apiPost("/cashflow", { direction: modal?.direction, ...values });
    }
    reload();
  };

  const remove = async (id: string) => {
    await apiDelete(`/cashflow/${id}`);
    reload();
  };

  const post = async () => {
    setPosting(true);
    setPosted(null);
    try {
      const r = await apiPost<{ posted: number; skipped: number }>("/cashflow/post");
      setPosted(`Posted ${r.posted} to the ledger.`);
    } finally {
      setPosting(false);
    }
  };

  const tooltipStyle = { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, color: "var(--text)" };

  const actions = (
    <>
      <button className="btn btn--sm" onClick={() => setModal({ direction: "inflow" })}>+ Inflow</button>
      <button className="btn btn--sm btn--ghost" onClick={() => setModal({ direction: "outflow" })}>+ Outflow</button>
      <button className="btn btn--sm btn--ghost" onClick={post} disabled={posting} title="Create transactions from recurring items (with an account) for this month">
        {posting ? "…" : "Post"}
      </button>
    </>
  );

  return (
    <Card title="Recurring cashflow (plan)" className={className} action={actions}>
      <Async state={summary}>
        {(s) => (
          <>
            <div className="metric-row">
              <div className="metric-block"><div className="label">Inflow</div><div className="value pos">{money(s.monthly_inflow, s.currency)}</div></div>
              <div className="metric-block"><div className="label">Outflow</div><div className="value neg">{money(s.monthly_outflow, s.currency)}</div></div>
              <div className="metric-block"><div className="label">Net</div><div className={"value " + (num(s.monthly_net) >= 0 ? "pos" : "neg")}>{money(s.monthly_net, s.currency)}</div></div>
            </div>
            <ResponsiveContainer width="100%" height={170}>
              <BarChart data={[{ name: "per month", Inflow: num(s.monthly_inflow), Outflow: num(s.monthly_outflow) }]} barGap={8}>
                <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
                <XAxis dataKey="name" tick={{ fill: axis, fontSize: 12 }} stroke={grid} />
                <YAxis tick={{ fill: axis, fontSize: 12 }} stroke={grid} width={68} tickFormatter={(v) => money(v)} />
                <Tooltip formatter={(v: number) => money(v)} cursor={{ fill: "transparent" }} contentStyle={tooltipStyle} />
                <Bar dataKey="Inflow" fill="var(--positive)" radius={[6, 6, 0, 0]} />
                <Bar dataKey="Outflow" fill="var(--negative)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </>
        )}
      </Async>

      {posted && <div className="muted" style={{ fontSize: 12 }}>{posted}</div>}

      <Async state={items}>
        {(list) => {
          const active = list.filter((i) => i.active);
          if (active.length === 0)
            return <div className="empty">No recurring items yet — add an inflow or outflow above.</div>;
          return (
            <ul className="list" style={{ marginTop: 10 }}>
              {active.map((i) => (
                <li key={i.id}>
                  <span style={{ cursor: "pointer" }} onClick={() => setModal({ direction: i.direction, item: i })} title="Edit">
                    <span className="li-main">{i.name}</span> <span className="li-sub">· {titleCase(i.cadence)}</span>
                  </span>
                  <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span className={"tnum " + (i.direction === "inflow" ? "pos" : "neg")}>
                      {i.direction === "inflow" ? "+" : "−"}{money(i.amount, i.currency)}
                    </span>
                    <button className="btn btn--ghost btn--sm" style={{ padding: "2px 7px" }} onClick={() => remove(i.id)} title="Delete">×</button>
                  </span>
                </li>
              ))}
            </ul>
          );
        }}
      </Async>

      {modal && (
        <Modal title={modal.item ? "Edit cashflow item" : modal.direction === "inflow" ? "Add inflow" : "Add outflow"} onClose={() => setModal(null)}>
          <CashflowForm initial={modal.item} accounts={accounts.data ?? []} onClose={() => setModal(null)} onSubmit={submit} />
        </Modal>
      )}
    </Card>
  );
}
