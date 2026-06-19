import { useApi } from "../hooks/useApi";
import type { AlertOut } from "../api/types";
import { Card } from "./Card";
import { Async } from "./Async";

export function AlertsCard() {
  const state = useApi<AlertOut[]>("/alerts");
  return (
    <Card title="Alerts">
      <Async state={state}>
        {(alerts) =>
          alerts.length === 0 ? (
            <div className="empty">All good — no alerts. 🎉</div>
          ) : (
            <ul className="alerts">
              {alerts.map((a, i) => (
                <li key={i} className={"alert alert--" + a.level}>
                  {a.message}
                </li>
              ))}
            </ul>
          )
        }
      </Async>
    </Card>
  );
}
