"""Build a copy-paste prompt that an AI agent (e.g. the Claude browser extension) can use to
fill the German tax return in Mein ELSTER from the computed EÜR.

We deliberately do NOT hard-code ELSTER Zeile numbers (they shift between tax years). Instead
we group the figures by the Anlage EÜR's semantic sections and instruct the agent to place
each value into the matching field of the current form.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from backend.tax.eur import EurResult


def _eur(value: Decimal) -> str:
    """Whole-euro string for an ELSTER field (it rounds to euros on most EÜR lines)."""
    return str(int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


def build_elster_prompt(business, tax_profile, year_input, eur: EurResult) -> str:
    name = business.name or business.company_name or "der/die Steuerpflichtige"
    anlage = "Anlage S (selbständige Arbeit, Freiberufler)" if eur.business_type == "freiberufler" \
        else "Anlage G (Gewerbebetrieb)"
    klein = (
        "Kleinunternehmer nach §19 UStG — es wird KEINE Umsatzsteuer ausgewiesen; "
        "Beträge sind Bruttobeträge ohne USt-Ausweis."
        if eur.is_kleinunternehmer else
        "Regelbesteuerung (kein Kleinunternehmer) — Umsatzsteuer ist relevant, wird hier aber "
        "NICHT berechnet; bitte USt separat behandeln."
    )

    lines: list[str] = []
    lines.append(
        f"Du hilfst mir, meine deutsche Steuererklärung für das Steuerjahr {eur.year} in "
        f"Mein ELSTER (www.elster.de) auszufüllen. Steuerpflichtig: {name}."
    )
    lines.append("")
    lines.append("Kontext:")
    lines.append(f"- Einkunftsart: {anlage} + Anlage EÜR (Einnahmenüberschussrechnung).")
    lines.append(f"- Umsatzsteuer-Status: {klein}")
    lines.append(
        "- Hinweis: Ordne jeden Wert dem passenden Feld der AKTUELLEN Anlage EÜR zu "
        "(die Zeilennummern ändern sich je Jahr). Frage mich vor dem endgültigen Absenden."
    )
    lines.append("")

    lines.append("== Betriebseinnahmen ==")
    lines.append(f"- Betriebseinnahmen (umsatzsteuerfrei/§19): {_eur(eur.income)} EUR")
    lines.append("")

    lines.append("== Betriebsausgaben ==")
    direct = [l for l in eur.expense_lines if l.key == "direct"]
    mixed = [l for l in eur.expense_lines if l.key == "mixed"]
    allowances = [l for l in eur.expense_lines if l.key in ("home_office", "travel")]

    if direct:
        lines.append("Voll abziehbare Betriebsausgaben (100%, nach Kategorie):")
        for l in direct:
            lines.append(f"  - {l.label}: {_eur(l.amount)} EUR")
    if mixed:
        lines.append("Gemischt genutzte Ausgaben (anteilig betrieblich):")
        for l in mixed:
            lines.append(
                f"  - {l.label}: {_eur(l.amount)} EUR "
                f"(von {_eur(l.gross or Decimal(0))} EUR gesamt)"
            )
    if allowances:
        lines.append("Pauschalen / besondere Ausgaben:")
        for l in allowances:
            lines.append(f"  - {l.label}: {_eur(l.amount)} EUR")
    lines.append(f"Summe Betriebsausgaben: {_eur(eur.expense_total)} EUR")
    lines.append("")

    lines.append("== Ergebnis ==")
    lines.append(f"- Gewinn (Einnahmenüberschuss): {_eur(eur.profit)} EUR")
    lines.append(
        f"  → trägt in die Gewinnermittlung der {anlage} ein."
    )
    lines.append("")

    lines.append("== Angaben zum Arbeitszimmer / Homeoffice / Fahrten ==")
    if eur.home_office_mode == "flat":
        lines.append(f"- Homeoffice-Pauschale: {year_input.home_office_days} Tage à 6 EUR (max. 1.260 EUR/Jahr).")
    elif eur.home_office_mode == "room":
        if tax_profile.room_use_pauschale:
            lines.append("- Häusliches Arbeitszimmer: Jahrespauschale 1.260 EUR.")
        else:
            lines.append(
                f"- Häusliches Arbeitszimmer: {tax_profile.room_sqm} m² von {tax_profile.home_total_sqm} m², "
                f"anteilige Jahreskosten aus {tax_profile.home_annual_cost} EUR."
            )
    else:
        lines.append("- Kein Arbeitszimmer / keine Homeoffice-Pauschale angesetzt.")
    if eur.business_km > 0:
        lines.append(f"- Betrieblich gefahrene Kilometer: {eur.business_km} km × {eur.km_rate} EUR/km.")
    lines.append("")

    lines.append("== Schätzung Einkommensteuer (nur Orientierung, KEINE Steuerberatung) ==")
    lines.append(f"- Übriges zu versteuerndes Einkommen (z.B. Gehalt): {_eur(eur.other_income)} EUR")
    lines.append(
        f"- Geschätzte zusätzliche Einkommensteuer auf den Gewinn (§32a, Tarif {eur.tariff_year}): "
        f"{_eur(eur.tax_estimate)} EUR"
    )
    lines.append("")
    lines.append(
        "Bitte führe mich Schritt für Schritt durch die passenden Felder in Mein ELSTER und "
        "trage die obigen Werte ein. Weise mich auf fehlende Angaben hin und sende nichts ohne "
        "meine ausdrückliche Bestätigung ab."
    )
    return "\n".join(lines)
