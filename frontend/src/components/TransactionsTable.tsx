import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { apiPatch } from "../api/client";
import type { CategoryOut, TransactionOut } from "../api/types";
import { money, num, shortDate } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

export function TransactionsTable() {
  const txns = useApi<TransactionOut[]>("/transactions");
  const cats = useApi<CategoryOut[]>("/categories");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all"); // all | uncategorized | <category_id>

  const recategorize = async (id: string, categoryId: string) => {
    await apiPatch(`/transactions/${id}`, { category_id: categoryId || null });
    txns.reload();
  };

  const action = <span className="muted">{txns.data?.length ?? 0} total</span>;

  return (
    <Card title="Transactions" action={action} wide>
      <div className="toolbar">
        <input
          className="input"
          placeholder="Search payee / description…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          className="select"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="all">All categories</option>
          <option value="uncategorized">Uncategorized</option>
          {cats.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
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
            return (
              <div className="empty">
                No matching transactions. Add one or import a CSV via the API.
              </div>
            );
          return (
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Payee</th>
                  <th>Description</th>
                  <th className="amount">Amount</th>
                  <th>Category</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((t) => (
                  <tr key={t.id}>
                    <td>{shortDate(t.ts)}</td>
                    <td>
                      {t.raw_payee || "—"}{" "}
                      {t.is_recurring && (
                        <span className="badge badge--recurring">recurring</span>
                      )}
                    </td>
                    <td className="muted">{t.description || "—"}</td>
                    <td className={"amount " + (num(t.amount) >= 0 ? "pos" : "neg")}>
                      {money(t.amount, t.currency)}
                    </td>
                    <td>
                      <select
                        className="select"
                        value={t.category_id || ""}
                        onChange={(e) => recategorize(t.id, e.target.value)}
                      >
                        <option value="">— none —</option>
                        {cats.data?.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          );
        }}
      </Async>
    </Card>
  );
}
