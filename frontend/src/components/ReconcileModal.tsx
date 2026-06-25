import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import type { AccountOut, ReconcilePreviewOut, ReconciliationOut } from "../api/types";
import { money, num, shortDate } from "../lib/format";
import { Modal } from "./Modal";

// Assert an account's real balance on a date; the app shows the drift vs the computed (sum of
// transactions) balance and books a single adjusting entry so the balance matches reality.
export function ReconcileModal({
  account,
  onClose,
  onDone,
}: {
  account: AccountOut;
  onClose: () => void;
  onDone: () => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [asserted, setAsserted] = useState(String(num(account.latest_balance ?? 0)));
  const [asOf, setAsOf] = useState(today);
  const [preview, setPreview] = useState<ReconcilePreviewOut | null>(null);
  const [history, setHistory] = useState<ReconciliationOut[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<ReconciliationOut[]>(`/accounts/${account.id}/reconcile/history`)
      .then(setHistory)
      .catch(() => {});
  }, [account.id]);

  // Live preview of computed-vs-asserted whenever the inputs change.
  useEffect(() => {
    if (asserted === "" || Number.isNaN(parseFloat(asserted))) {
      setPreview(null);
      return;
    }
    let active = true;
    apiPost<ReconcilePreviewOut>(`/accounts/${account.id}/reconcile/preview`, {
      asserted_balance: asserted,
      as_of: asOf,
    })
      .then((p) => active && setPreview(p))
      .catch((e) => active && setError(e instanceof Error ? e.message : "Failed"));
    return () => {
      active = false;
    };
  }, [account.id, asserted, asOf]);

  const commit = async () => {
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/accounts/${account.id}/reconcile`, {
        asserted_balance: asserted,
        as_of: asOf,
      });
      onDone();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
      setBusy(false);
    }
  };

  const delta = preview ? num(preview.delta) : 0;

  return (
    <Modal title={`Reconcile — ${account.name}`} onClose={onClose}>
      <form className="form" onSubmit={(e) => { e.preventDefault(); commit(); }}>
        <div className="field-row">
          <div className="field">
            <label>Real balance</label>
            <input className="input" type="number" step="0.01" value={asserted} autoFocus
              onChange={(e) => setAsserted(e.target.value)} />
          </div>
          <div className="field">
            <label>As of</label>
            <input className="input" type="date" value={asOf} max={today}
              onChange={(e) => setAsOf(e.target.value)} />
          </div>
        </div>

        {preview && (
          <div className="metric-row">
            <div className="metric-block">
              <div className="label">Computed</div>
              <div className="value">{money(preview.computed_balance, preview.currency)}</div>
            </div>
            <div className="metric-block">
              <div className="label">You assert</div>
              <div className="value">{money(preview.asserted_balance, preview.currency)}</div>
            </div>
            <div className="metric-block">
              <div className="label">Adjustment</div>
              <div className={"value " + (delta > 0 ? "pos" : delta < 0 ? "neg" : "")}>
                {delta === 0 ? "—" : money(preview.delta, preview.currency)}
              </div>
            </div>
          </div>
        )}

        <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
          {Math.abs(delta) < 0.005
            ? "Already matches — nothing to adjust."
            : "Books one labelled “Balance reconciliation” entry (excluded from income/expense and the EÜR) so the balance matches reality."}
        </div>

        {error && <div className="error">{error}</div>}

        {history.length > 0 && (
          <div className="muted" style={{ fontSize: 11, marginTop: 8 }}>
            Last reconciled {shortDate(history[0].as_of)} ({money(history[0].asserted_balance)}).
          </div>
        )}

        <div className="form__actions">
          <button type="button" className="btn btn--ghost" onClick={onClose}>Cancel</button>
          <button className="btn" type="submit" disabled={busy || Math.abs(delta) < 0.005}>
            {busy ? "…" : "Book adjustment"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
