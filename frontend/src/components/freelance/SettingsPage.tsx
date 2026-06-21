import { useEffect, useState } from "react";
import { apiPatch } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import type { BusinessProfileOut } from "../../api/types";
import { Card } from "../Card";
import { Async } from "../Async";
import { LANGUAGES } from "./helpers";

function ProfileForm({ profile, onSaved }: { profile: BusinessProfileOut; onSaved: () => void }) {
  const [name, setName] = useState(profile.name);
  const [companyName, setCompanyName] = useState(profile.company_name);
  const [phone, setPhone] = useState(profile.phone);
  const [email, setEmail] = useState(profile.email);
  const [address, setAddress] = useState(profile.address);
  const [postalCode, setPostalCode] = useState(profile.postal_code);
  const [city, setCity] = useState(profile.city);
  const [iban, setIban] = useState(profile.iban);
  const [bic, setBic] = useState(profile.bic);
  const [taxNumber, setTaxNumber] = useState(profile.tax_number);
  const [kleinunternehmer, setKleinunternehmer] = useState(profile.is_kleinunternehmer);
  const [vatNote, setVatNote] = useState(profile.vat_note);
  const [intro, setIntro] = useState(profile.intro_text);
  const [language, setLanguage] = useState(profile.default_language);
  const [rate, setRate] = useState(profile.default_hourly_rate);
  const [nextNo, setNextNo] = useState(String(profile.next_invoice_number));
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Re-sync if the underlying profile changes (e.g. after a save elsewhere).
  useEffect(() => {
    setName(profile.name);
    setCompanyName(profile.company_name);
    setPhone(profile.phone);
    setEmail(profile.email);
    setAddress(profile.address);
    setPostalCode(profile.postal_code);
    setCity(profile.city);
    setIban(profile.iban);
    setBic(profile.bic);
    setTaxNumber(profile.tax_number);
    setKleinunternehmer(profile.is_kleinunternehmer);
    setVatNote(profile.vat_note);
    setIntro(profile.intro_text);
    setLanguage(profile.default_language);
    setRate(profile.default_hourly_rate);
    setNextNo(String(profile.next_invoice_number));
  }, [profile]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await apiPatch("/business-profile", {
        name, company_name: companyName, phone, email, address,
        postal_code: postalCode, city, iban, bic,
        tax_number: taxNumber, is_kleinunternehmer: kleinunternehmer, vat_note: vatNote,
        intro_text: intro, default_language: language, default_hourly_rate: rate || "0",
        next_invoice_number: parseInt(nextNo || "0", 10) || 0,
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
          <label>Your name</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)}
            placeholder="André Kipphard" />
        </div>
        <div className="field">
          <label>Company name (optional)</label>
          <input className="input" value={companyName} onChange={(e) => setCompanyName(e.target.value)}
            placeholder="Kipphard Studio" />
        </div>
      </div>
      <div className="field-row">
        <div className="field">
          <label>Phone</label>
          <input className="input" value={phone} onChange={(e) => setPhone(e.target.value)}
            placeholder="+49 …" />
        </div>
        <div className="field">
          <label>Email</label>
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
      </div>
      <div className="field">
        <label>Street (Straße + Nr.)</label>
        <input className="input" value={address} onChange={(e) => setAddress(e.target.value)}
          placeholder="Erlenbusch 12" />
      </div>
      <div className="field-row">
        <div className="field" style={{ flex: "0 0 120px" }}>
          <label>Postleitzahl</label>
          <input className="input" value={postalCode} onChange={(e) => setPostalCode(e.target.value)}
            placeholder="33106" />
        </div>
        <div className="field">
          <label>City (Stadt) — also the invoice "place"</label>
          <input className="input" value={city} onChange={(e) => setCity(e.target.value)}
            placeholder="Paderborn" />
        </div>
      </div>
      <div className="muted" style={{ fontSize: 12, marginTop: -6 }}>
        The invoice sender block is built from your name/company + these three fields.
      </div>
      <div className="field-row">
        <div className="field">
          <label>IBAN</label>
          <input className="input" value={iban} onChange={(e) => setIban(e.target.value)} />
        </div>
        <div className="field">
          <label>BIC</label>
          <input className="input" value={bic} onChange={(e) => setBic(e.target.value)} />
        </div>
      </div>
      <div className="field">
        <label>Tax number</label>
        <input className="input" value={taxNumber} onChange={(e) => setTaxNumber(e.target.value)} />
      </div>

      <label className="check">
        <input type="checkbox" checked={kleinunternehmer}
          onChange={(e) => setKleinunternehmer(e.target.checked)} />
        <span>Kleinunternehmer (§19 UStG) — don't charge VAT on invoices</span>
      </label>
      {!kleinunternehmer && (
        <div className="muted" style={{ fontSize: 12, marginTop: -6 }}>
          New invoices will add 19% VAT (net → gross).
        </div>
      )}

      <div className="field-row">
        <div className="field">
          <label>Default invoice language</label>
          <select className="select" value={language}
            onChange={(e) => setLanguage(e.target.value as BusinessProfileOut["default_language"])}>
            {LANGUAGES.map((l) => (
              <option key={l.value} value={l.value}>{l.label}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Default hourly rate (€)</label>
          <input className="input" type="number" min="0" step="0.01" value={rate}
            onChange={(e) => setRate(e.target.value)} />
        </div>
        <div className="field">
          <label>Next invoice number</label>
          <input className="input" type="number" min="0" step="1" value={nextNo}
            onChange={(e) => setNextNo(e.target.value)} />
        </div>
      </div>
      <div className="field">
        <label>§19 / VAT note (optional — overrides the default)</label>
        <textarea className="input" rows={2} value={vatNote} onChange={(e) => setVatNote(e.target.value)}
          placeholder="Leave blank to use the standard note for the chosen language" />
      </div>
      <div className="field">
        <label>Default intro text (optional — overrides the default)</label>
        <textarea className="input" rows={3} value={intro} onChange={(e) => setIntro(e.target.value)}
          placeholder="Leave blank to use the standard greeting for the chosen language" />
      </div>
      {error && <div className="error">{error}</div>}
      <div className="form__actions" style={{ alignItems: "center" }}>
        {saved && <span className="muted" style={{ marginRight: "auto", color: "var(--positive)" }}>Saved ✓</span>}
        <button className="btn" type="submit" disabled={busy}>{busy ? "…" : "Save settings"}</button>
      </div>
    </form>
  );
}

export function SettingsPage() {
  const state = useApi<BusinessProfileOut>("/business-profile");
  return (
    <Card title="Business profile">
      <Async state={state}>
        {(profile) => <ProfileForm profile={profile} onSaved={() => state.reload()} />}
      </Async>
    </Card>
  );
}
