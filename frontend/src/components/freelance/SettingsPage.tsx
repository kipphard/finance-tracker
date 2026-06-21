import { useEffect, useState } from "react";
import { apiPatch, apiPost } from "../../api/client";
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
  const [paymentTerms, setPaymentTerms] = useState(String(profile.payment_terms_days));
  const [paymentInfo, setPaymentInfo] = useState(profile.payment_info);
  const [vatNote, setVatNote] = useState(profile.vat_note);
  const [intro, setIntro] = useState(profile.intro_text);
  const [language, setLanguage] = useState(profile.default_language);
  const [rate, setRate] = useState(profile.default_hourly_rate);
  const [nextNo, setNextNo] = useState(String(profile.next_invoice_number));
  const [digestCadence, setDigestCadence] = useState(profile.digest_cadence);
  const [digestInvoices, setDigestInvoices] = useState(profile.digest_invoices);
  const [digestTime, setDigestTime] = useState(profile.digest_time);
  const [digestFinance, setDigestFinance] = useState(profile.digest_finance);
  const [testMsg, setTestMsg] = useState<string | null>(null);
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
    setPaymentTerms(String(profile.payment_terms_days));
    setPaymentInfo(profile.payment_info);
    setVatNote(profile.vat_note);
    setIntro(profile.intro_text);
    setLanguage(profile.default_language);
    setRate(profile.default_hourly_rate);
    setNextNo(String(profile.next_invoice_number));
    setDigestCadence(profile.digest_cadence);
    setDigestInvoices(profile.digest_invoices);
    setDigestTime(profile.digest_time);
    setDigestFinance(profile.digest_finance);
  }, [profile]);

  const sendTestDigest = async () => {
    setTestMsg(null);
    try {
      const r = await apiPost<{ to: string }>("/business-profile/digest-test");
      setTestMsg(`Test digest sent to ${r.to}`);
    } catch (err) {
      setTestMsg(err instanceof Error ? err.message : "Failed to send");
    }
  };

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
        payment_terms_days: parseInt(paymentTerms || "0", 10) || 0, payment_info: paymentInfo,
        intro_text: intro, default_language: language, default_hourly_rate: rate || "0",
        next_invoice_number: parseInt(nextNo || "0", 10) || 0,
        digest_cadence: digestCadence, digest_invoices: digestInvoices,
        digest_time: digestTime, digest_finance: digestFinance,
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
        <div className="field" style={{ flex: "0 0 160px" }}>
          <label>Payment term (days)</label>
          <input className="input" type="number" min="0" step="1" value={paymentTerms}
            onChange={(e) => setPaymentTerms(e.target.value)} placeholder="14" />
        </div>
        <div className="field">
          <label>Payment info / link on invoice (optional)</label>
          <input className="input" value={paymentInfo} onChange={(e) => setPaymentInfo(e.target.value)}
            placeholder="z.B. Zahlung an Revolut: revolut.me/andre" />
        </div>
      </div>
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
      <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "6px 0" }} />
      <div className="field">
        <label>Notification digest (email)</label>
        <div className="field-row">
          <div className="field" style={{ flex: "0 0 160px" }}>
            <select className="select" value={digestCadence}
              onChange={(e) => setDigestCadence(e.target.value as BusinessProfileOut["digest_cadence"])}>
              <option value="off">Off</option>
              <option value="weekly">Weekly (Mon)</option>
              <option value="monthly">Monthly (1st)</option>
            </select>
          </div>
          <div className="field" style={{ flexDirection: "row", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
            <label className="check"><input type="checkbox" checked={digestInvoices}
              onChange={(e) => setDigestInvoices(e.target.checked)} disabled={digestCadence === "off"} /><span>Invoices</span></label>
            <label className="check"><input type="checkbox" checked={digestTime}
              onChange={(e) => setDigestTime(e.target.checked)} disabled={digestCadence === "off"} /><span>Time</span></label>
            <label className="check"><input type="checkbox" checked={digestFinance}
              onChange={(e) => setDigestFinance(e.target.checked)} disabled={digestCadence === "off"} /><span>Finance</span></label>
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 6 }}>
          <button type="button" className="btn btn--ghost btn--sm" onClick={sendTestDigest}>Send test digest now</button>
          {testMsg && <span className="muted" style={{ fontSize: 12 }}>{testMsg}</span>}
        </div>
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
