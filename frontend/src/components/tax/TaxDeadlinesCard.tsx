import { useApi } from "../../hooks/useApi";
import type { TaxCalendarOut } from "../../api/types";
import { money, shortDate } from "../../lib/format";
import { Card } from "../Card";
import { Async } from "../Async";

const KIND_ICON: Record<string, string> = {
  est_vorauszahlung: "💶",
  ust_voranmeldung: "🧾",
  est_erklaerung: "📅",
};

// German freelancer tax deadlines for the year: quarterly Einkommensteuer-Vorauszahlung, the
// (quarterly) Umsatzsteuer-Voranmeldung for non-Kleinunternehmer, and the EÜR filing date.
export function TaxDeadlinesCard({ year }: { year: number }) {
  const state = useApi<TaxCalendarOut>(`/tax/calendar?year=${year}`);
  const today = new Date().toISOString().slice(0, 10);
  return (
    <Card title={`Steuertermine ${year}`}>
      <Async state={state}>
        {(c) => (
          <>
            <ul className="list">
              {c.deadlines.map((d, i) => (
                <li key={i} style={{ opacity: d.date < today ? 0.5 : 1 }}>
                  <span>
                    <span className="li-main">{KIND_ICON[d.kind] ?? "•"} {d.label}</span>
                    <span className="li-sub"> · {shortDate(d.date)}</span>
                    {d.note && <span className="li-sub"> · {d.note}</span>}
                  </span>
                  {d.amount != null && <span className="amount neg">{money(d.amount)}</span>}
                </li>
              ))}
            </ul>
            <div className="muted" style={{ fontSize: 11, marginTop: 8 }}>
              {c.is_kleinunternehmer
                ? "Kleinunternehmer (§19) — keine Umsatzsteuer-Voranmeldung."
                : "Regelbesteuerung — vierteljährliche Umsatzsteuer-Voranmeldung."}{" "}
              Vorauszahlung geschätzt; gesetzliche Stichtage (ohne Wochenend-/Feiertagsverschiebung).
              Keine Steuerberatung.
            </div>
          </>
        )}
      </Async>
    </Card>
  );
}
