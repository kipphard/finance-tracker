import { useApi } from "../hooks/useApi";
import type { AccountOut } from "../api/types";
import { money, titleCase } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

export function AccountsCard() {
  const state = useApi<AccountOut[]>("/accounts");
  return (
    <Card title="Accounts">
      <Async state={state}>
        {(accounts) =>
          accounts.length === 0 ? (
            <div className="empty">No accounts yet (add via /api/accounts).</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Source</th>
                  <th className="amount">Balance</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((a) => (
                  <tr key={a.id}>
                    <td>{a.name}</td>
                    <td>{titleCase(a.type)}</td>
                    <td>
                      <span className="badge">{a.connector}</span>
                    </td>
                    <td className="amount">
                      {a.latest_balance != null ? money(a.latest_balance, a.currency) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        }
      </Async>
    </Card>
  );
}
