import { useState } from "react";
import { Card } from "./Card";

const KEY = "ft_playbook_collapsed";

const STEPS: { t: string; d: string }[] = [
  { t: "Know your numbers", d: "Income, fixed costs, what's left over. ✓ You're here." },
  {
    t: "Starter buffer (€1–2k)",
    d: "A small airbag so one surprise doesn't bounce you back onto debt — not the full fund yet.",
  },
  {
    t: "Grab free money",
    d: "Employer match — German VL (~€40/mo) or bAV. A match is an instant 50–100% return; take it whenever it's offered.",
  },
  {
    t: "Kill high-interest debt (>~7–8%)",
    d: "Credit cards, Dispo (often 10–14%!), consumer loans. Paying it off is a guaranteed, risk-free return — the best 'investment' there is.",
  },
  {
    t: "Full emergency fund",
    d: "3–6 months of essentials (track it in the Emergency fund card).",
  },
  {
    t: "Invest — the S&P Sparplan",
    d: "The default home for every surplus euro, forever.",
  },
  {
    t: "Low-interest debt (<~4%)",
    d: "Mortgage, cheap car loan — just pay on schedule. The market out-earns the rate, so overpaying is a (mild) mistake.",
  },
];

export function PlaybookCard({ className }: { className?: string }) {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(KEY) === "1";
    } catch {
      return false;
    }
  });

  const toggle = () => {
    const v = !collapsed;
    setCollapsed(v);
    try {
      localStorage.setItem(KEY, v ? "1" : "0");
    } catch {
      /* ignore */
    }
  };

  const action = (
    <button className="btn btn--ghost btn--sm" onClick={toggle}>
      {collapsed ? "Show" : "Hide"}
    </button>
  );

  return (
    <Card title="Money playbook" className={className} action={action}>
      {collapsed ? (
        <div className="muted" style={{ fontSize: 13 }}>
          Highest guaranteed return wins: starter buffer → free money → kill high-interest debt →
          full emergency fund → invest. Income grows in parallel.
        </div>
      ) : (
        <>
          <div className="playbook__principle">
            💡 <b>Money flows to the highest guaranteed return.</b> Paying off a 12% debt is a
            risk-free 12% — better than the market's ~7% with risk. So the interest rate decides
            what comes before investing and what comes after.
          </div>

          <ol className="playbook__steps">
            {STEPS.map((s, i) => (
              <li key={i}>
                <span className="playbook__num">{i + 1}</span>
                <span>
                  <b>{s.t}</b> — <span className="muted">{s.d}</span>
                </span>
              </li>
            ))}
          </ol>

          <div className="playbook__notes">
            <div className="playbook__note">
              <b>🚀 Income runs in parallel.</b> Raises and side income aren't a step — they're
              always-on, and the highest-leverage lever: you can't save more than 100%, but income
              has no ceiling. A €500/mo raise beats any budgeting tweak. Don't wait until debt's
              gone to start.
            </div>
            <div className="playbook__note">
              <b>🎯 Debt order = avalanche.</b> Pay every minimum, keep the small buffer, then throw
              every spare euro at the <i>highest-rate</i> debt until it's dead — then roll that
              freed-up payment onto the next. (Smallest-balance-first "snowball" is costlier but
              more motivating.)
            </div>
          </div>

          <div className="muted" style={{ fontSize: 11, marginTop: 12 }}>
            Rules of thumb — about as close to consensus as personal finance gets. Not licensed
            financial advice.
          </div>
        </>
      )}
    </Card>
  );
}
