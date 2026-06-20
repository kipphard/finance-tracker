import { useRef, useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiDelete, apiOpen, apiUpload } from "../api/client";
import type { AttachmentOut } from "../api/types";
import { Modal } from "./Modal";
import { Async } from "./Async";

function kb(size: number): string {
  return size < 1024 * 1024
    ? `${Math.max(1, Math.round(size / 1024))} KB`
    : `${(size / 1024 / 1024).toFixed(1)} MB`;
}

export function AttachmentsModal({ txnId, onClose }: { txnId: string; onClose: () => void }) {
  const state = useApi<AttachmentOut[]>(`/transactions/${txnId}/attachments`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const upload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await apiUpload(`/transactions/${txnId}/attachments`, file);
      state.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const remove = async (id: string) => {
    await apiDelete(`/attachments/${id}`);
    state.reload();
  };

  return (
    <Modal title="Attachments (invoices / receipts)" onClose={onClose}>
      <Async state={state}>
        {(files) =>
          files.length === 0 ? (
            <div className="empty">No files attached yet.</div>
          ) : (
            <ul className="list">
              {files.map((f) => (
                <li key={f.id}>
                  <span style={{ minWidth: 0, flex: 1, overflow: "hidden" }}>
                    <span className="li-main" title={f.filename}
                      style={{ display: "block", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {f.filename}
                    </span>
                    <span className="li-sub">{kb(f.size)}</span>
                  </span>
                  <span style={{ display: "flex", gap: 8, flex: "0 0 auto" }}>
                    <button className="btn btn--sm" onClick={() => apiOpen(`/attachments/${f.id}`)}>
                      View
                    </button>
                    <button className="btn btn--ghost btn--sm" style={{ padding: "2px 8px" }}
                      onClick={() => remove(f.id)} title="Delete">
                      Delete
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          )
        }
      </Async>

      {error && <div className="error">{error}</div>}

      <div style={{ marginTop: 14 }}>
        <label className="btn btn--sm" style={{ cursor: busy ? "default" : "pointer" }}>
          {busy ? "Uploading…" : "+ Upload PDF / image"}
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf,image/png,image/jpeg,image/webp"
            style={{ display: "none" }}
            onChange={upload}
            disabled={busy}
          />
        </label>
        <span className="muted" style={{ fontSize: 12, marginLeft: 10 }}>max 10 MB</span>
      </div>
    </Modal>
  );
}
