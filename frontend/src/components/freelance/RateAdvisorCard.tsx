import { useState } from "react";
import { useApi } from "../../hooks/useApi";
import type { AdvisorOut } from "../../api/types";
import { money, num } from "../../lib/format";
import { Card } from "../Card";
import { Async } from "../Async";

const round1 = (n: number) => Math.round(n * 10) / 10;

// null runway = net-positive (no burn, effectively infinite).
const runwayMonths = (net: number, liquid: number): number | null =>
  net < 0 && liquid > 0 ? liquid / -net : null;
const runwayLabel = (m: number | null) => (m == null ? "∞" : `${m.toFixed(1)} mo`);

export function RateAdvisorCard() {
  const state = useApi<AdvisorOut>("/reports/advisor");
  return (
    <Card title="Rate advisor & what-if">
      <Async state={state}>{(a) => <AdvisorBody a={a} />}</Async>
    </Card>
  );
}

function AdvisorBody({ a }: { a: AdvisorOut }) {
  const cur = a.currency;
  const billableMonth = num(a.billable_hours_month);
  const marginal = num(a.marginal_tax_rate); // 0..1
  const monthlyIncome = num(a.monthly_income);
  const monthlyNet = num(a.monthly_net);
  const monthlyFixed = num(a.monthly_fixed);
  const liquid = num(a.liquid);
  const annualProfit = num(a.annual_profit);
  const annualTax = num(a.annual_tax);
  const currentRate = num(a.default_hourly_rate);

  // ----- Rate advisor -----
  // Default billable hours/week to your trailing actuals — but only if there's enough tracked
  // time to be meaningful; otherwise fall back to a sane 30 (avoids a silly rate from ~0 hours).
  const derivedHoursWeek = round1((billableMonth * 12) / 52);
  const [takeHome, setTakeHome] = useState(String(Math.max(0, Math.round(num(a.sustainable_pay)))));
  const [hoursWeek, setHoursWeek] = useState(String(derivedHoursWeek >= 5 ? derivedHoursWeek : 30));
  const [weeksYear, setWeeksYear] = useState("46");

  const hoursMonth = (num(hoursWeek) * num(weeksYear)) / 12;
  // To net `takeHome` after fixed costs and tax: gross = costs + takeHome / (1 − marginal rate).
  const grossNeeded = monthlyFixed + (marginal < 1 ? num(takeHome) / (1 - marginal) : num(takeHome));
  const recommendedRate = hoursMonth > 0 ? grossNeeded / hoursMonth : null;
  const rateDelta = recommendedRate != null && currentRate > 0 ? recommendedRate - currentRate : null;

  // ----- What-if -----
  const [ratePct, setRatePct] = useState(0);
  const [dropId, setDropId] = useState("");
  const [oneOff, setOneOff] = useState("");

  const dropped = a.clients.find((c) => c.id === dropId);
  const dIncome = monthlyIncome * (ratePct / 100) - (dropped ? num(dropped.monthly_income) : 0);
  const newNet = monthlyNet + dIncome;
  const newLiquid = liquid - num(oneOff);
  const newProfit = annualProfit + dIncome * 12;
  const newTax = Math.max(0, annualTax + dIncome * 12 * marginal);
  const baseRunway = runwayMonths(monthlyNet, liquid);
  const newRunway = runwayMonths(newNet, newLiquid);

  // Color a scenario value vs its baseline (higher tax is bad; higher everything else is good).
  const tone = (now: number, next: number, higherIsGood = true) => {
    const better = higherIsGood ? next > now : next < now;
    const worse = higherIsGood ? next < now : next > now;
    return better ? "var(--positive)" : worse ? "var(--negative)" : "var(--text)";
  };
  const runwayTone = () => {
    const n = baseRunway ?? Infinity;
    const x = newRunway ?? Infinity;
    return x > n ? "var(--positive)" : x < n ? "var(--negative)" : "var(--text)";
  };

  return (
    <>
      {/* ===== What should I charge? ===== */}
      <h3 className="tax-subhead">What should I charge?</h3>
      <div className="field-row">
        <div className="field">
          <label>Desired take-home /mo</label>
          <input className="input" type="number" min="0" step="100" value={takeHome}
            onChange={(e) => setTakeHome(e.target.value)} />
        </div>
        <div className="field">
          <label>Billable hours /week</label>
          <input className="input" type="number" min="0" step="1" value={hoursWeek}
            onChange={(e) => setHoursWeek(e.target.value)} />
        </div>
        <div className="field">
          <label>Weeks /year</label>
          <input className="input" type="number" min="1" max="52" step="1" value={weeksYear}
            onChange={(e) => setWeeksYear(e.target.value)} />
        </div>
      </div>

      <div className="metric-row">
        <div className="metric-block">
          <div className="label">Charge about</div>
          <div className="value">{recommendedRate != null ? `${money(recommendedRate, cur)}/h` : "—"}</div>
        </div>
        <div className="metric-block">
          <div className="label">Your current rate</div>
          <div className="value">{currentRate > 0 ? `${money(currentRate, cur)}/h` : "—"}</div>
        </div>
        {rateDelta != null && Math.abs(rateDelta) >= 0.5 && (
          <div className="metric-block">
            <div className="label">{rateDelta > 0 ? "Raise by" : "Already above by"}</div>
            <div className="value" style={{ color: rateDelta > 0 ? "var(--warn)" : "var(--positive)" }}>
              {money(Math.abs(rateDelta), cur)}/h
            </div>
          </div>
        )}
      </div>
      <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>
        Rate that nets your target after fixed costs ({money(monthlyFixed, cur)}/mo) and tax
        (~{Math.round(marginal * 100)}% marginal), across {round1(hoursMonth)} billable h/mo.
        {derivedHoursWeek < 5 && " (Default 30 h/wk — track more time to base hours on your actuals.)"}
      </div>

      {/* ===== What-if ===== */}
      <h3 className="tax-subhead" style={{ marginTop: 18 }}>What-if scenarios</h3>
      <div className="field">
        <label>Change rates: {ratePct > 0 ? "+" : ""}{ratePct}%</label>
        <input type="range" min={-50} max={50} step={5} value={ratePct}
          onChange={(e) => setRatePct(Number(e.target.value))} style={{ width: "100%" }} />
      </div>
      <div className="field-row">
        <div className="field">
          <label>Lose a client</label>
          <select className="select" value={dropId} onChange={(e) => setDropId(e.target.value)}
            disabled={a.clients.length === 0}>
            <option value="">— none —</option>
            {a.clients.map((c) => (
              <option key={c.id} value={c.id}>{c.name} ({money(c.monthly_income, cur)}/mo)</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>One-off purchase</label>
          <input className="input" type="number" min="0" step="500" placeholder="0"
            value={oneOff} onChange={(e) => setOneOff(e.target.value)} />
        </div>
      </div>

      <div className="table-scroll">
        <table>
          <thead>
            <tr><th>Impact</th><th className="amount">Now</th><th className="amount">Scenario</th></tr>
          </thead>
          <tbody>
            <tr>
              <td>Monthly net</td>
              <td className="amount">{money(monthlyNet, cur)}</td>
              <td className="amount" style={{ color: tone(monthlyNet, newNet) }}>{money(newNet, cur)}</td>
            </tr>
            <tr>
              <td>Cash runway</td>
              <td className="amount">{runwayLabel(baseRunway)}</td>
              <td className="amount" style={{ color: runwayTone() }}>{runwayLabel(newRunway)}</td>
            </tr>
            <tr>
              <td>Annual profit</td>
              <td className="amount">{money(annualProfit, cur)}</td>
              <td className="amount" style={{ color: tone(annualProfit, newProfit) }}>{money(newProfit, cur)}</td>
            </tr>
            <tr>
              <td>Est. income tax</td>
              <td className="amount">{money(annualTax, cur)}</td>
              <td className="amount" style={{ color: tone(annualTax, newTax, false) }}>{money(newTax, cur)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="muted" style={{ fontSize: 11, marginTop: 8 }}>
        Sliders apply to your trailing figures; tax uses a flat ~{Math.round(marginal * 100)}% marginal
        rate, so it's a rough planning aid — not tax advice.
      </div>
    </>
  );
}
