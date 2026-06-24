"""Turn billable time entries into invoice line items.

Default ("none") is one line per entry, chronological — the long-standing behaviour. The
grouping modes bundle entries by project / ISO-week / calendar-month into a single line each,
summing the hours, with a theme header plus the distinct tidied tasks as bullets.

Shared by the manual invoice-create path (`api/invoices.py`) and the recurring-invoice
materializer (`invoicing/recurring.py`).
"""
from __future__ import annotations

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from backend.invoicing.i18n import texts
from backend.invoicing.text import flatten
from backend.persistence.models import InvoiceItem

GROUP_MODES = ("none", "project", "week", "month")


def _q(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _bulleted(theme: str, descriptions: list[str]) -> str:
    """Theme line + one '• ' bullet per distinct (case-insensitive) tidied task description."""
    seen: set[str] = set()
    bullets: list[str] = []
    for raw in descriptions:
        line = flatten(raw)
        key = line.lower()
        if line and key not in seen:
            seen.add(key)
            bullets.append(f"• {line}")
    return theme + ("\n" + "\n".join(bullets) if bullets else "")


def _bucket(entry, group_by: str, lang: str, project_name) -> tuple:
    """(hashable key, theme header) for one entry under the given grouping mode."""
    t = texts(lang)
    if group_by == "project":
        return (entry.project_id, project_name(entry.project_id) or t["general"])
    d = entry.started_at.date()
    if group_by == "week":
        iso_year, iso_week, _ = d.isocalendar()
        monday = d - timedelta(days=d.weekday())
        sunday = monday + timedelta(days=6)
        sep = "" if lang == "de" else ", "  # DE date_short ends in a dot, EN needs a comma
        rng = f"{monday.strftime(t['date_short'])}–{sunday.strftime(t['date_short'])}{sep}{sunday.year}"
        return ((iso_year, iso_week), f"{t['week']} {iso_week} ({rng})")
    # month
    return ((d.year, d.month), f"{t['months'][d.month - 1]} {d.year}")


def build_items(entries, rate_for, project_name, group_by: str = "none", lang: str = "de"):
    """Build invoice line items from time entries.

    entries:      iterable of TimeEntry (sorted here by started_at).
    rate_for:     entry -> Decimal hourly rate (project override → client rate).
    project_name: project_id|None -> str|None, for the "project" grouping header.
    group_by:     "none" (one line per entry) | "project" | "week" | "month".
    Returns (items, net_total).
    """
    entries = sorted(entries, key=lambda e: e.started_at)
    if group_by not in GROUP_MODES:
        group_by = "none"

    if group_by == "none":
        items: list[InvoiceItem] = []
        net = Decimal(0)
        for i, e in enumerate(entries):
            hrs = _q(Decimal(e.minutes) / Decimal(60))
            rate = rate_for(e)
            amount = _q(hrs * rate)
            net += amount
            items.append(InvoiceItem(
                description=flatten(e.description) or "Service",
                hours=hrs, rate=rate, amount=amount, position=i,
            ))
        return items, net

    # Bucket by (group key, rate) so one line never mixes rates; preserve first-seen order.
    buckets: dict = {}
    order: list = []
    for e in entries:
        key, theme = _bucket(e, group_by, lang, project_name)
        rate = rate_for(e)
        bk = (key, str(rate))
        b = buckets.get(bk)
        if b is None:
            b = {"theme": theme, "rate": rate, "minutes": 0, "descs": []}
            buckets[bk] = b
            order.append(bk)
        b["minutes"] += e.minutes
        if e.description:
            b["descs"].append(e.description)

    items, net = [], Decimal(0)
    for i, bk in enumerate(order):
        b = buckets[bk]
        hrs = _q(Decimal(b["minutes"]) / Decimal(60))
        amount = _q(hrs * b["rate"])
        net += amount
        items.append(InvoiceItem(
            description=_bulleted(b["theme"], b["descs"]) or "Service",
            hours=hrs, rate=b["rate"], amount=amount, position=i,
        ))
    return items, net
