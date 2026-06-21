import { useState } from "react";
import { apiPost } from "../../api/client";
import type { BusinessProfileOut, ClientOut, InvoiceOut } from "../../api/types";
import { Modal } from "../Modal";
import { invoiceEmail } from "./helpers";

// Compose + send an invoice email from the server (SMTP). All fields are pre-filled from
// your settings + the client and can be overwritten before sending. The PDF is attached.
export function InvoiceEmailModal({
  invoice,
  client,
  profile,
  onClose,
  onSent,
}: {
  invoice: InvoiceOut;
  client?: ClientOut;
  profile?: BusinessProfileOut;
  onClose: () => void;
  onSent: () => void;
}) {
  const sender = profile?.company_name || profile?.name || "";
  const preset = invoiceEmail(invoice.language, invoice.number, sender);
  const [from, setFrom] = useState(profile?.email ?? "");
  const [to, setTo] = useState(client?.email ?? "");
  const [subject, setSubject] = useState(preset.subject);
  const [body, setBody] = useState(preset.body);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!to.trim()) return setError("Add a recipient email");
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/invoices/${invoice.id}/email`, { from, to, subject, body });
      onSent();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title={`Email invoice ${invoice.number}`} className="modal--md" onClose={onClose}>
      <form className="form" onSubmit={send}>
        <div className="field-row">
          <div className="field">
            <label>From</label>
            <input className="input" type="email" value={from} onChange={(e) => setFrom(e.target.value)}
              placeholder="you@gmail.com" />
          </div>
          <div className="field">
            <label>To</label>
            <input className="input" type="email" value={to} onChange={(e) => setTo(e.target.value)}
              placeholder="client@example.com" required />
          </div>
        </div>
        <div className="field">
          <label>Subject</label>
          <input className="input" value={subject} onChange={(e) => setSubject(e.target.value)} />
        </div>
        <div className="field">
          <label>Message</label>
          <textarea className="input" rows={7} value={body} onChange={(e) => setBody(e.target.value)} />
        </div>
        <div className="muted" style={{ fontSize: 12 }}>
          📎 The invoice PDF (Rechnung{invoice.number}.pdf) is attached automatically.
        </div>
        {error && <div className="error">{error}</div>}
        <div className="form__actions">
          <button type="button" className="btn btn--ghost" onClick={onClose}>Cancel</button>
          <button className="btn" type="submit" disabled={busy}>{busy ? "Sending…" : "Send email"}</button>
        </div>
      </form>
    </Modal>
  );
}
