import { useEffect, useState } from "react";
import { apiDownload, apiGet, apiPatch } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import type { EurReportOut, ElsterPromptOut, TaxYearInputOut } from "../../api/types";
import { money, num } from "../../lib/format";
import { Card } from "../Card";
import { Async } from "../Async";

const NOW = new Date().getFullYear();
const YEARS = [NOW, NOW - 1, NOW - 2, NOW - 3, NOW - 4];

const BUCKET_LABEL: Record<string, string> = {
  income: "Einnahme",
  direct: "Ausgabe (100%)",
  mixed: "Gemischt",
};

export function TaxOverviewPage() {
  // Default to the last completed calendar year — that's the one you file.
  const [year, setYear] = useState(NOW - 1);
  const state = useApi<EurReportOut>(`/tax/eur?year=${year}`);

  return (
    <>
      <div className="toolbar" style={{ marginBottom: 16, alignItems: "flex-end" }}>
        <div className="field" style={{ flex: "0 0 160px" }}>
          <label>Tax year</label>
          <select className="select" value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {YEARS.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button
            className="btn btn--ghost btn--sm"
            onClick={() => apiDownload(`/tax/export.csv?year=${year}`, `euer_${year}.csv`)}
          >
            ⬇ CSV
          </button>
        </div>
      </div>

      <Async state={state}>
        {(r) => (
          <div className="card-stack">
            <EurSummary report={r} />
            <RefundCard report={r} />
            <YearInputsCard year={year} />
            <ElsterCard year={year} />
            <LineItemsCard report={r} />
          </div>
        )}
      </Async>
    </>
  );
}

function EurSummary({ report: r }: { report: EurReportOut }) {
  const estimate = num(r.tax_estimate);
  return (
    <Card title={`Einnahmenüberschussrechnung (EÜR) ${r.year}`}>
      <div className="metric-row">
        <div className="metric-block">
          <div className="label">Betriebseinnahmen</div>
          <div className="value pos">{money(r.income)}</div>
        </div>
        <div className="metric-block">
          <div className="label">Betriebsausgaben</div>
          <div className="value neg">{money(r.expense_total)}</div>
        </div>
        <div className="metric-block">
          <div className="label">Gewinn (EÜR)</div>
          <div className={"value " + (num(r.profit) >= 0 ? "pos" : "neg")}>{money(r.profit)}</div>
        </div>
      </div>

      <div className="muted" style={{ fontSize: 12, margin: "4px 0 12px" }}>
        {r.is_kleinunternehmer
          ? "Kleinunternehmer (§19 UStG) — keine Umsatzsteuer; Beträge sind brutto."
          : "Regelbesteuerung — Umsatzsteuer ist relevant, wird hier aber nicht berechnet."}
        {" · "}
        {r.business_type === "freiberufler" ? "Freiberufler (Anlage S)" : "Gewerbe (Anlage G)"}
      </div>

      <h3 className="tax-subhead">Betriebsausgaben im Detail</h3>
      {r.expense_lines.length === 0 ? (
        <div className="empty">Keine abziehbaren Ausgaben für {r.year}.</div>
      ) : (
        <ul className="list">
          {r.expense_lines.map((l, i) => (
            <li key={i}>
              <span>
                <span className="li-main">{l.label}</span>
                {l.gross && (
                  <span className="li-sub"> · von {money(l.gross)}</span>
                )}
                {l.count > 0 && <span className="li-sub"> · {l.count}×</span>}
              </span>
              <span className="tnum neg">{money(l.amount)}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="tax-estimate">
        <div>
          <div className="label">Geschätzte Einkommensteuer auf den Gewinn</div>
          <div className={"value " + (estimate >= 0 ? "neg" : "pos")}>
            {estimate >= 0 ? money(r.tax_estimate) : `− ${money(Math.abs(estimate))}`}
          </div>
        </div>
        <div className="muted" style={{ fontSize: 12 }}>
          §32a-Tarif {r.tariff_year}, aufgesetzt auf übrige Einkünfte von {money(r.other_income)}.
          {estimate < 0 && " Der Verlust senkt deine Steuer."}
          <br />
          <strong>Nur eine grobe Schätzung — keine Steuerberatung.</strong> Soli und Kirchensteuer
          sind nicht enthalten.
        </div>
      </div>
    </Card>
  );
}

function RefundCard({ report: r }: { report: EurReportOut }) {
  const zve = num(r.other_income) + num(r.profit);
  const balance = num(r.refund_or_owed); // > 0 = Nachzahlung (you owe), < 0 = Erstattung (refund)
  const isRefund = balance < 0;
  const settled = Math.abs(balance) < 0.005;
  return (
    <Card title={`Einkommensteuer gesamt — Erstattung / Nachzahlung ${r.year}`}>
      <ul className="list">
        <li>
          <span className="li-main">Zu versteuerndes Einkommen (Gehalt + Gewinn)</span>
          <span className="tnum">{money(zve)}</span>
        </li>
        <li>
          <span className="li-main">Einkommensteuer (gesamt)</span>
          <span className="tnum neg">{money(r.tax_with)}</span>
        </li>
        <li>
          <span className="li-main">− Einbehaltene Lohnsteuer</span>
          <span className="tnum pos">{money(r.withheld_lohnsteuer)}</span>
        </li>
        <li>
          <span className="li-main">− Einkommensteuer-Vorauszahlungen</span>
          <span className="tnum pos">{money(r.income_tax_prepaid)}</span>
        </li>
      </ul>
      <div className="tax-estimate">
        <div>
          <div className="label">
            {settled ? "Ausgeglichen" : isRefund ? "Voraussichtliche Erstattung" : "Voraussichtliche Nachzahlung"}
          </div>
          <div className={"value " + (settled ? "" : isRefund ? "pos" : "neg")}>
            {money(Math.abs(balance))}
          </div>
        </div>
        <div className="muted" style={{ fontSize: 12 }}>
          Gesamte Einkommensteuer auf Gehalt + Gewinn (§32a-Tarif {r.tariff_year}) minus bereits
          gezahlter Lohnsteuer und Vorauszahlungen.{" "}
          <strong>Nur eine grobe Schätzung — keine Steuerberatung.</strong> Soli und Kirchensteuer
          sind nicht enthalten.
        </div>
      </div>
    </Card>
  );
}

function YearInputsCard({ year }: { year: number }) {
  const state = useApi<TaxYearInputOut>(`/tax/year/${year}`);
  return (
    <Card title={`Angaben für ${year}`}>
      <Async state={state}>
        {(data) => <YearInputsForm key={year} year={year} data={data} />}
      </Async>
    </Card>
  );
}

function YearInputsForm({ year, data }: { year: number; data: TaxYearInputOut }) {
  const [otherIncome, setOtherIncome] = useState(data.other_taxable_income);
  const [lohnsteuer, setLohnsteuer] = useState(data.withheld_lohnsteuer);
  const [prepaid, setPrepaid] = useState(data.income_tax_prepaid);
  const [homeDays, setHomeDays] = useState(String(data.home_office_days));
  const [km, setKm] = useState(data.business_km);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await apiPatch(`/tax/year/${year}`, {
        other_taxable_income: otherIncome || "0",
        withheld_lohnsteuer: lohnsteuer || "0",
        income_tax_prepaid: prepaid || "0",
        home_office_days: parseInt(homeDays || "0", 10) || 0,
        business_km: km || "0",
      });
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="form" onSubmit={submit}>
      <div className="field-row">
        <div className="field">
          <label>Bruttoarbeitslohn / übrige Einkünfte (z.B. Gehalt) (€)</label>
          <input className="input" type="number" min="0" step="0.01" value={otherIncome}
            onChange={(e) => setOtherIncome(e.target.value)} />
        </div>
        <div className="field">
          <label>Einbehaltene Lohnsteuer (Lohnsteuerbescheinigung) (€)</label>
          <input className="input" type="number" min="0" step="0.01" value={lohnsteuer}
            onChange={(e) => setLohnsteuer(e.target.value)} />
        </div>
        <div className="field">
          <label>Einkommensteuer-Vorauszahlungen (€)</label>
          <input className="input" type="number" min="0" step="0.01" value={prepaid}
            onChange={(e) => setPrepaid(e.target.value)} />
        </div>
      </div>
      <div className="field-row">
        <div className="field" style={{ flex: "0 0 200px" }}>
          <label>Homeoffice-Tage</label>
          <input className="input" type="number" min="0" max="365" step="1" value={homeDays}
            onChange={(e) => setHomeDays(e.target.value)} />
        </div>
        <div className="field" style={{ flex: "0 0 200px" }}>
          <label>Betrieblich gefahrene km</label>
          <input className="input" type="number" min="0" step="1" value={km}
            onChange={(e) => setKm(e.target.value)} />
        </div>
      </div>
      <div className="muted" style={{ fontSize: 12, marginTop: -4 }}>
        Bruttoarbeitslohn, einbehaltene Lohnsteuer und Vorauszahlungen ergeben die geschätzte
        Erstattung/Nachzahlung. Homeoffice-Tage zählen nur, wenn unter Settings
        „Homeoffice-Pauschale" gewählt ist (6 €/Tag, max. 1.260 €).
      </div>
      {error && <div className="error">{error}</div>}
      <div className="form__actions" style={{ alignItems: "center" }}>
        {saved && <span className="muted" style={{ marginRight: "auto", color: "var(--positive)" }}>Saved ✓</span>}
        <button className="btn" type="submit" disabled={busy}>{busy ? "…" : "Save"}</button>
      </div>
    </form>
  );
}

function ElsterCard({ year }: { year: number }) {
  const [prompt, setPrompt] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset when the year changes so a stale prompt isn't shown.
  useEffect(() => {
    setPrompt(null);
    setCopied(false);
  }, [year]);

  const generate = async () => {
    setBusy(true);
    setError(null);
    setCopied(false);
    try {
      const r = await apiGet<ElsterPromptOut>(`/tax/elster-prompt?year=${year}`);
      setPrompt(r.prompt);
      try {
        await navigator.clipboard.writeText(r.prompt);
        setCopied(true);
      } catch {
        /* clipboard may be blocked — the textarea below still lets the user copy manually */
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  const action = (
    <button className="btn btn--sm" onClick={generate} disabled={busy}>
      {busy ? "…" : "Generate ELSTER prompt"}
    </button>
  );

  return (
    <Card title="ELSTER helper" action={action}>
      <div className="muted" style={{ fontSize: 13 }}>
        Erzeugt einen fertigen Text mit allen EÜR-Werten, den du in die Claude-Browser-Erweiterung
        (oder eine andere KI) einfügen kannst, um beim Ausfüllen der Anlage EÜR in Mein ELSTER zu
        helfen.
      </div>
      {error && <div className="error" style={{ marginTop: 10 }}>{error}</div>}
      {copied && (
        <div className="muted" style={{ color: "var(--positive)", marginTop: 10 }}>
          In die Zwischenablage kopiert ✓
        </div>
      )}
      {prompt && (
        <textarea
          className="input"
          readOnly
          rows={14}
          value={prompt}
          style={{ marginTop: 12, fontFamily: "ui-monospace, monospace", fontSize: 12 }}
          onFocus={(e) => e.currentTarget.select()}
        />
      )}
    </Card>
  );
}

function LineItemsCard({ report: r }: { report: EurReportOut }) {
  return (
    <Card title="Erfasste Buchungen">
      {r.line_items.length === 0 ? (
        <div className="empty">Keine als geschäftlich markierten oder gemischt genutzten Buchungen in {r.year}.</div>
      ) : (
        <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Datum</th>
              <th>Empfänger</th>
              <th>Kategorie</th>
              <th>Art</th>
              <th className="amount">Betrag</th>
              <th className="amount">Anrechenbar</th>
            </tr>
          </thead>
          <tbody>
            {r.line_items.map((i, idx) => (
              <tr key={idx}>
                <td>{i.date}</td>
                <td>{i.payee || "—"}</td>
                <td>{i.category || "—"}</td>
                <td>
                  <span className="badge">{BUCKET_LABEL[i.bucket] ?? i.bucket}</span>
                  {i.percent != null && (
                    <span className="li-sub"> · {num(i.percent)}%</span>
                  )}
                </td>
                <td className={"amount tnum " + (num(i.amount) >= 0 ? "pos" : "neg")}>{money(i.amount)}</td>
                <td className="amount tnum">{money(i.deductible)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      )}
    </Card>
  );
}
