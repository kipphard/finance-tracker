// Shared formatting + datetime helpers for the Freelance section.

// Minutes → "1h 30m" / "45m" / "2h".
export function fmtDuration(minutes: number): string {
  const m = Math.max(0, Math.round(minutes));
  const h = Math.floor(m / 60);
  const rem = m % 60;
  if (h === 0) return `${rem}m`;
  if (rem === 0) return `${h}h`;
  return `${h}h ${rem}m`;
}

// Decimal-string hours → "1,5 h" (German), trailing zeros trimmed.
export function fmtHours(value: string | number | null | undefined): string {
  const n = typeof value === "string" ? parseFloat(value) : value ?? 0;
  if (!Number.isFinite(n)) return "0 h";
  const s = (n as number)
    .toFixed(2)
    .replace(/\.?0+$/, "")
    .replace(".", ",");
  return `${s} h`;
}

// Minutes → decimal hours (for live timer math etc).
export function minutesToHours(minutes: number): number {
  return minutes / 60;
}

// Milliseconds → "HH:MM:SS" for the live running timer.
export function fmtClock(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(Math.floor(total / 3600))}:${pad(Math.floor((total % 3600) / 60))}:${pad(total % 60)}`;
}

// A Date → a "YYYY-MM-DDTHH:mm" string for <input type="datetime-local"> (local time).
export function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

// A "YYYY-MM-DDTHH:mm" local-input string → an ISO UTC string for the API.
export function localInputToIso(value: string): string {
  return new Date(value).toISOString();
}

// ISO string → "19.06.2026, 14:30" (German).
export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export const INVOICE_STATUSES = ["draft", "sent", "paid"] as const;
export type InvoiceStatus = (typeof INVOICE_STATUSES)[number];

// Short codes keep the (often cramped) language picker readable.
export const LANGUAGES: { value: string; label: string }[] = [
  { value: "de", label: "DE" },
  { value: "en", label: "EN" },
];

// Default invoice intro per language (mirrors the backend i18n defaults).
export const INTRO_DEFAULTS: Record<string, string> = {
  de:
    "Sehr geehrte Damen und Herren,\n\nvielen Dank für die gute Zusammenarbeit. " +
    "Hiermit stelle ich Ihnen die folgenden Leistungen in Rechnung:",
  en:
    "Dear Sir or Madam,\n\nthank you for the successful cooperation. " +
    "I hereby invoice you for the following services as agreed:",
};

// Texts the app itself generated (current + legacy English) — safe to auto-replace on a
// language switch; anything else is treated as the user's own wording and left alone.
const KNOWN_INTROS = new Set(
  [
    "",
    INTRO_DEFAULTS.de,
    INTRO_DEFAULTS.en,
    "Dear Sir or Madam,\n\nthank you for the successful cooperation so far. " +
      "I hereby invoice you for the following services as agreed:",
  ].map((s) => s.trim())
);

export function isDefaultIntro(text: string): boolean {
  return KNOWN_INTROS.has((text || "").trim());
}

// Mahnstufe label for a given reminder level (1 = friendly reminder, 2 = 1. Mahnung, …).
export function reminderStage(level: number, language: string): string {
  const de = ["", "Zahlungserinnerung", "1. Mahnung", "2. Mahnung", "3. Mahnung"];
  const en = ["", "Payment reminder", "1st reminder", "2nd reminder", "Final reminder"];
  const arr = language === "de" ? de : en;
  return arr[Math.min(level, 4)] || arr[4];
}

// A localized subject + body for a payment reminder / Mahnung at the next escalation level.
export function reminderEmail(
  language: string, nextLevel: number, number: string, sender: string,
  total: string, deadline: string
) {
  const stage = reminderStage(nextLevel, language);
  if (language === "de") {
    const intro =
      nextLevel <= 1
        ? `sicher ist es Ihrer Aufmerksamkeit entgangen, dass die Rechnung Nr. ${number} über ${total} noch offen ist. Wir möchten Sie freundlich an die Zahlung erinnern`
        : `trotz unserer bisherigen Erinnerung ist die Rechnung Nr. ${number} über ${total} weiterhin offen. Wir fordern Sie hiermit nachdrücklich auf, den Betrag zu begleichen`;
    return {
      subject: `${stage} – Rechnung Nr. ${number}`,
      body:
        `Sehr geehrte Damen und Herren,\n\n${intro} und bitten um Ausgleich bis zum ${deadline}.\n\n` +
        `Die betreffende Rechnung finden Sie zur Erinnerung im Anhang. Sollten Sie die Zahlung ` +
        `zwischenzeitlich veranlasst haben, betrachten Sie dieses Schreiben bitte als gegenstandslos.\n\n` +
        `Mit freundlichen Grüßen\n${sender}`,
    };
  }
  const intro =
    nextLevel <= 1
      ? `this is a friendly reminder that invoice no. ${number} for ${total} is still outstanding`
      : `despite our previous reminder, invoice no. ${number} for ${total} remains unpaid, and we must now urge you to settle it`;
  return {
    subject: `${stage} – Invoice no. ${number}`,
    body:
      `Dear Sir or Madam,\n\n${intro}. Please arrange payment by ${deadline}.\n\n` +
      `The invoice is attached for your reference. If you have already paid, please disregard this message.\n\n` +
      `Kind regards\n${sender}`,
  };
}

// A localized default subject + body for emailing an invoice.
export function invoiceEmail(language: string, number: string, sender: string) {
  if (language === "de") {
    return {
      subject: `Rechnung Nr. ${number}`,
      body:
        `Sehr geehrte Damen und Herren,\n\n` +
        `anbei erhalten Sie die Rechnung Nr. ${number} als PDF. ` +
        `Bei Fragen stehe ich Ihnen gerne zur Verfügung.\n\n` +
        `Mit freundlichen Grüßen\n${sender}`,
    };
  }
  return {
    subject: `Invoice No. ${number}`,
    body:
      `Dear Sir or Madam,\n\n` +
      `please find attached invoice no. ${number} as a PDF. ` +
      `If you have any questions, I'm happy to help.\n\n` +
      `Kind regards\n${sender}`,
  };
}
