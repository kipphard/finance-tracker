import { useState } from "react";
import { apiPatch } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import type { CategoryOut, TaxProfileOut } from "../../api/types";
import { Card } from "../Card";
import { Async } from "../Async";

export function TaxSettingsPage() {
  const profile = useApi<TaxProfileOut>("/tax/profile");
  const categories = useApi<CategoryOut[]>("/categories");

  return (
    <Card title="Tax settings">
      <Async state={profile}>
        {(p) => (
          <Async state={categories}>
            {(cats) => <ProfileForm profile={p} categories={cats} onSaved={() => profile.reload()} />}
          </Async>
        )}
      </Async>
    </Card>
  );
}

function ProfileForm({
  profile,
  categories,
  onSaved,
}: {
  profile: TaxProfileOut;
  categories: CategoryOut[];
  onSaved: () => void;
}) {
  const [tag, setTag] = useState(profile.freelance_tag);
  const [businessType, setBusinessType] = useState(profile.business_type);
  const [kmRate, setKmRate] = useState(profile.km_rate);
  const [homeMode, setHomeMode] = useState(profile.home_office_mode);
  const [roomPauschale, setRoomPauschale] = useState(profile.room_use_pauschale);
  const [roomSqm, setRoomSqm] = useState(profile.room_sqm ?? "");
  const [homeTotalSqm, setHomeTotalSqm] = useState(profile.home_total_sqm ?? "");
  const [homeAnnualCost, setHomeAnnualCost] = useState(profile.home_annual_cost);

  // Mixed-use percentages keyed by category id (as strings for the inputs).
  const [rates, setRates] = useState<Record<string, string>>(() => {
    const out: Record<string, string> = {};
    for (const [id, pct] of Object.entries(profile.mixed_use_rates ?? {})) {
      out[id] = String(pct);
    }
    return out;
  });

  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const expenseCats = categories.filter((c) => c.kind === "expense");
  const setRate = (id: string, value: string) => setRates((r) => ({ ...r, [id]: value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);

    const mixed: Record<string, number> = {};
    for (const [id, value] of Object.entries(rates)) {
      const pct = parseFloat(value);
      if (Number.isFinite(pct) && pct > 0) mixed[id] = pct;
    }

    try {
      await apiPatch("/tax/profile", {
        freelance_tag: tag.trim() || "freelance",
        business_type: businessType,
        km_rate: kmRate || "0",
        home_office_mode: homeMode,
        room_use_pauschale: roomPauschale,
        room_sqm: roomSqm === "" ? null : roomSqm,
        home_total_sqm: homeTotalSqm === "" ? null : homeTotalSqm,
        home_annual_cost: homeAnnualCost || "0",
        mixed_use_rates: mixed,
      });
      setSaved(true);
      onSaved();
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
          <label>Freelance tag</label>
          <input className="input" value={tag} onChange={(e) => setTag(e.target.value)}
            placeholder="freelance" />
        </div>
        <div className="field">
          <label>Business type</label>
          <select className="select" value={businessType}
            onChange={(e) => setBusinessType(e.target.value as TaxProfileOut["business_type"])}>
            <option value="freiberufler">Freiberufler (Anlage S)</option>
            <option value="gewerbe">Gewerbe (Anlage G)</option>
          </select>
        </div>
      </div>
      <div className="muted" style={{ fontSize: 12, marginTop: -6 }}>
        Transaktionen mit diesem Tag zählen als Betriebseinnahmen/-ausgaben (zu 100%).
      </div>

      <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "6px 0" }} />

      <div className="field">
        <label>Arbeitszimmer / Homeoffice</label>
        <select className="select" value={homeMode}
          onChange={(e) => setHomeMode(e.target.value as TaxProfileOut["home_office_mode"])}>
          <option value="none">Keins</option>
          <option value="flat">Homeoffice-Pauschale (6 €/Tag, max. 1.260 €)</option>
          <option value="room">Häusliches Arbeitszimmer (eigener Raum)</option>
        </select>
      </div>
      {homeMode === "room" && (
        <>
          <label className="check">
            <input type="checkbox" checked={roomPauschale}
              onChange={(e) => setRoomPauschale(e.target.checked)} />
            <span>Jahrespauschale 1.260 € verwenden (statt tatsächlicher Kosten)</span>
          </label>
          {!roomPauschale && (
            <div className="field-row">
              <div className="field">
                <label>Raum (m²)</label>
                <input className="input" type="number" min="0" step="0.1" value={roomSqm}
                  onChange={(e) => setRoomSqm(e.target.value)} />
              </div>
              <div className="field">
                <label>Wohnung gesamt (m²)</label>
                <input className="input" type="number" min="0" step="0.1" value={homeTotalSqm}
                  onChange={(e) => setHomeTotalSqm(e.target.value)} />
              </div>
              <div className="field">
                <label>Jahreskosten Wohnung (Miete + NK) (€)</label>
                <input className="input" type="number" min="0" step="0.01" value={homeAnnualCost}
                  onChange={(e) => setHomeAnnualCost(e.target.value)} />
              </div>
            </div>
          )}
        </>
      )}

      <div className="field" style={{ flex: "0 0 220px" }}>
        <label>km-Pauschale für Geschäftsfahrten (€/km)</label>
        <input className="input" type="number" min="0" step="0.01" value={kmRate}
          onChange={(e) => setKmRate(e.target.value)} />
      </div>

      <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "6px 0" }} />

      <div className="field">
        <label>Gemischt genutzte Kategorien (betrieblicher Anteil in %)</label>
        <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
          z.B. Internet 50%, Mobile 60%. Der Prozentsatz wird auf alle Buchungen dieser Kategorie
          angewendet, die NICHT mit „{tag || "freelance"}" getaggt sind (sonst doppelte Zählung).
        </div>
        {expenseCats.length === 0 ? (
          <div className="empty">Noch keine Ausgaben-Kategorien.</div>
        ) : (
          <ul className="list">
            {expenseCats.map((c) => (
              <li key={c.id}>
                <span className="li-main">{c.name}</span>
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <input
                    className="input"
                    type="number"
                    min="0"
                    max="100"
                    step="1"
                    placeholder="0"
                    value={rates[c.id] ?? ""}
                    onChange={(e) => setRate(c.id, e.target.value)}
                    style={{ width: 80, textAlign: "right" }}
                  />
                  <span className="muted">%</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {error && <div className="error">{error}</div>}
      <div className="form__actions" style={{ alignItems: "center" }}>
        {saved && <span className="muted" style={{ marginRight: "auto", color: "var(--positive)" }}>Saved ✓</span>}
        <button className="btn" type="submit" disabled={busy}>{busy ? "…" : "Save settings"}</button>
      </div>
    </form>
  );
}
