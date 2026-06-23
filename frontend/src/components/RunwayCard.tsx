import { useApi } from "../hooks/useApi";
import type { RunwayOut } from "../api/types";
import { money, num } from "../lib/format";
import { Card } from "./Card";
import { Async } from "./Async";

// How many months your liquid balance lasts at the current monthly net.
export function RunwayCard({ className }: { className?: string }) {
  const state = useApi<RunwayOut>("/reports/runway");
  return (
    <Card title="Cash runway" className={className}>
      <Async state={state}>
        {(r) => {
          const m = r.runway_months;
          return (
            <>
              <div className="metric-row">
                <div className="metric-block">
                  <div className="label">Runway</div>
                  <div className={"value " + (m != null && num(m) < 3 ? "neg" : "")}>
                    {m == null ? "∞" : `${num(m).toFixed(1)} mo`}
                  </div>
                </div>
                <div className="metric-block">
                  <div className="label">Liquid</div>
                  <div className="value">{money(r.liquid)}</div>
                </div>
                <div className="metric-block">
                  <div className="label">Monthly net</div>
                  <div className={"value " + (num(r.monthly_net) >= 0 ? "pos" : "neg")}>
                    {money(r.monthly_net)}
                  </div>
                </div>
              </div>
              <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
                {m == null
                  ? "You're net-positive — no burn, so runway is effectively unlimited."
                  : "Months your liquid (non-investment) balance covers the current monthly burn."}
                {num(r.earmarked) > 0 && (
                  <> · {money(r.earmarked)} tax reserve earmarked &amp; excluded.</>
                )}
              </div>
            </>
          );
        }}
      </Async>
    </Card>
  );
}
