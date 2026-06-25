import { useApi } from "../hooks/useApi";
import type { PaycheckOut } from "../api/types";
import { money, num } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

// "Pay yourself" / safe-to-spend: smooths lumpy freelance income into one sustainable monthly
// figure — trailing net minus the tax reserve and planned savings, capped by your liquid balance.
export function PaycheckCard({ className }: { className?: string }) {
  const state = useApi<PaycheckOut>("/reports/paycheck");
  return (
    <Card title="Sustainable monthly pay" className={className}>
      <Async state={state}>
        {(p) => (
          <>
            <div className="metric-row">
              <div className="metric-block">
                <div className="label">Pay yourself</div>
                <div className={"value " + (num(p.sustainable_pay) > 0 ? "pos" : "")}>
                  {money(p.sustainable_pay, p.currency)}
                </div>
              </div>
              <div className="metric-block">
                <div className="label">Avg monthly net</div>
                <div className="value">{money(p.trailing_net, p.currency)}</div>
              </div>
              <div className="metric-block">
                <div className="label">Liquid</div>
                <div className="value">{money(p.liquid, p.currency)}</div>
              </div>
            </div>

            <ul className="list" style={{ marginTop: 8 }}>
              {p.breakdown.map((l, i) => (
                <li key={i}>
                  <span className="li-main">{l.label}</span>
                  <span className={"amount " + (num(l.amount) < 0 ? "neg" : "")}>
                    {money(l.amount, p.currency)}
                  </span>
                </li>
              ))}
            </ul>

            <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
              {p.capped_by_liquid
                ? "Capped by your liquid balance — there isn't enough cash on hand to pay the full average net yet."
                : "What's left of your trailing average net after setting aside taxes and planned savings."}{" "}
              Fixed costs are already inside the net figure. A guide, not advice.
            </div>
          </>
        )}
      </Async>
    </Card>
  );
}
