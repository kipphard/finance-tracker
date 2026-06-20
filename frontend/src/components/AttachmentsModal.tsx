import { useEffect, useRef, useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiBlobUrl, apiDelete, apiUpload } from "../api/client";
import type { AttachmentOut } from "../api/types";
import { Modal } from "./Modal";
import { Async } from "./Async";

function kb(size: number): string {
  return size < 1024 * 1024
    ? `${Math.max(1, Math.round(size / 1024))} KB`
    : `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function AttachmentPreview({ file, onClose }: { file: AttachmentOut; onClose: () => void }) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let obj: string | null = null;
    let alive = true;
    apiBlobUrl(`/attachments/${file.id}`)
      .then((u) => {
        obj = u;
        if (alive) setUrl(u);
      })
      .catch((e) => {
        if (alive) setError(e instanceof Error ? e.message : "Failed to load");
      });
    return () => {
      alive = false;
      if (obj) URL.revokeObjectURL(obj);
    };
  }, [file.id]);

  const isImage = file.content_type.startsWith("image/");

  return (
    <Modal title={file.filename} onClose={onClose} className="modal--wide">
      {error ? (
        <div className="error">{error}</div>
      ) : !url ? (
        <div className="muted">Loading…</div>
      ) : isImage ? (
        <img src={url} alt={file.filename}
          style={{ maxWidth: "100%", maxHeight: "74vh", display: "block", margin: "0 auto", borderRadius: 8 }} />
      ) : (
        <iframe src={url} title={file.filename}
          style={{ width: "100%", height: "74vh", border: 0, borderRadius: 8, background: "#fff" }} />
      )}
      {url && (
        <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
          <a className="btn btn--sm" href={url} target="_blank" rel="noopener noreferrer">Open in new tab</a>
          <a className="btn btn--ghost btn--sm" href={url} download={file.filename}>Download</a>
        </div>
      )}
    </Modal>
  );
}

export function AttachmentsModal({ txnId, onClose }: { txnId: string; onClose: () => void }) {
  const state = useApi<AttachmentOut[]>(`/transactions/${txnId}/attachments`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<AttachmentOut | null>(null);
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
    <>
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
                    <button className="btn btn--sm" onClick={() => setPreview(f)}>
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
    {preview && <AttachmentPreview file={preview} onClose={() => setPreview(null)} />}
    </>
  );
}
