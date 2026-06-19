export function num(value: string | number | null | undefined): number {
  if (value == null) return 0;
  const n = typeof value === "string" ? parseFloat(value) : value;
  return Number.isFinite(n) ? n : 0;
}

export function money(value: string | number | null | undefined, currency = "EUR"): string {
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(num(value));
}

export function shortDate(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString("de-DE");
}

export function titleCase(value: string): string {
  return value.replace(/(^|[_\s])(\w)/g, (_, sep, ch) => (sep ? " " : "") + ch.toUpperCase());
}
