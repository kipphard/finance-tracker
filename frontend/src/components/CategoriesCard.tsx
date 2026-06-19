import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiDelete, apiPost } from "../api/client";
import type { CategoryOut } from "../api/types";
import { Card } from "./Card";
import { Async } from "./Async";
import { Modal } from "./Modal";

function CategoryForm({ onSubmit, onClose }: { onSubmit: (v: any) => Promise<void>; onClose: () => void }) {
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"expense" | "income">("expense");
  const [isFixed, setIsFixed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit({ name, kind, is_fixed: isFixed });
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
        <input className="input" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
      </div>
      <div className="field-row">
        <div className="field">
          <label>Kind</label>
          <select className="select" value={kind} onChange={(e) => setKind(e.target.value as any)}>
            <option value="expense">Expense</option>
            <option value="income">Income</option>
          </select>
        </div>
        <div className="field">
          <label>Fixed cost?</label>
          <label style={{ display: "flex", alignItems: "center", gap: 8, height: 38 }}>
            <input type="checkbox" checked={isFixed} onChange={(e) => setIsFixed(e.target.checked)} />
            <span className="muted">Fixed (vs variable)</span>
          </label>
        </div>
      </div>
      {error && <div className="error">{error}</div>}
      <div className="form__actions">
        <button type="button" className="btn btn--ghost" onClick={onClose}>Cancel</button>
        <button className="btn" type="submit" disabled={busy}>{busy ? "…" : "Add category"}</button>
      </div>
    </form>
  );
}

export function CategoriesCard({ className }: { className?: string }) {
  const state = useApi<CategoryOut[]>("/categories");
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const add = async (v: any) => {
    await apiPost("/categories", v);
    state.reload();
  };
  const seed = async () => {
    setBusy(true);
    try {
      await apiPost("/categories/seed");
      state.reload();
    } finally {
      setBusy(false);
    }
  };
  const remove = async (id: string) => {
    await apiDelete(`/categories/${id}`);
    state.reload();
  };

  const action = (
    <button className="btn btn--sm" onClick={() => setOpen(true)}>
      + Category
    </button>
  );

  return (
    <Card title="Categories" className={className} action={action}>
      <Async state={state}>
        {(categories) =>
          categories.length === 0 ? (
            <div className="empty">
              No categories yet.{" "}
              <button className="btn btn--ghost btn--sm" onClick={seed} disabled={busy}>
                {busy ? "…" : "Seed starter set"}
              </button>
            </div>
          ) : (
            <ul className="list">
              {categories.map((c) => (
                <li key={c.id}>
                  <span>
                    <span className="li-main">{c.name}</span>{" "}
                    <span className={"badge" + (c.is_fixed ? " badge--fixed" : "")}>
                      {c.kind}
                      {c.is_fixed ? " · fixed" : ""}
                    </span>
                  </span>
                  <button
                    className="btn btn--ghost btn--sm"
                    style={{ padding: "2px 7px" }}
                    onClick={() => remove(c.id)}
                    title="Delete"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )
        }
      </Async>

      {open && (
        <Modal title="Add category" onClose={() => setOpen(false)}>
          <CategoryForm onClose={() => setOpen(false)} onSubmit={add} />
        </Modal>
      )}
    </Card>
  );
}
