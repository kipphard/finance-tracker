import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiDelete, apiPost } from "../api/client";
import type { BudgetOut, BudgetStatusOut, CategoryOut } from "../api/types";
import { money, num } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

export function BudgetsCard() {
  const statuses = useApi<BudgetStatusOut[]>("/budgets/status");
  const budgets = useApi<BudgetOut[]>("/budgets");
  const categories = useApi<CategoryOut[]>("/categories");

  const [categoryId, setCategoryId] = useState("");
  const [limit, setLimit] = useState("");
  const [busy, setBusy] = useState(false);

  const budgeted = new Set((budgets.data ?? []).map((b) => b.category_id));
  const available = (categories.data ?? []).filter(
    (c) => c.kind === "expense" && !budgeted.has(c.id),
  );

  const reload = () => {
    statuses.reload();
    budgets.reload();
  };

  const add = async () => {
    if (!categoryId || !limit) return;
    setBusy(true);
    try {
      await apiPost("/budgets", { category_id: categoryId, monthly_limit: limit });
      setCategoryId("");
      setLimit("");
      reload();
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    await apiDelete(`/budgets/${id}`);
    reload();
  };

  return (
    <Card title="Budgets">
      <div className="toolbar">
        <select
          className="select"
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
        >
          <option value="">Add budget for…</option>
          {available.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <input
          className="input"
          type="number"
          min="0"
          step="0.01"
          placeholder="€ / month"
          value={limit}
          onChange={(e) => setLimit(e.target.value)}
          style={{ width: 110 }}
        />
        <button className="btn" onClick={add} disabled={busy || !categoryId || !limit}>
          Add
        </button>
      </div>

      <Async state={statuses}>
        {(rows) =>
          rows.length === 0 ? (
            <div className="empty">No budgets yet. Add one above.</div>
          ) : (
            <ul className="list">
              {rows.map((s) => {
                const pct = num(s.pct_used);
                const cls = s.over ? "is-over" : pct >= 90 ? "is-warn" : "";
                return (
                  <li key={s.budget_id} style={{ display: "block" }}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        marginBottom: 4,
                      }}
                    >
                      <span className="li-main">{s.category_name}</span>
                      <span className={s.over ? "neg" : "muted"}>
                        {money(s.spent)} / {money(s.monthly_limit)}
                        <button
                          className="btn btn--ghost"
                          style={{ padding: "0 6px", marginLeft: 8 }}
                          onClick={() => remove(s.budget_id)}
                          title="Remove budget"
                        >
                          ×
                        </button>
                      </span>
                    </div>
                    <div className="progress">
                      <div
                        className={"progress__bar " + cls}
                        style={{ width: Math.min(100, pct) + "%" }}
                      />
                    </div>
                  </li>
                );
              })}
            </ul>
          )
        }
      </Async>
    </Card>
  );
}
