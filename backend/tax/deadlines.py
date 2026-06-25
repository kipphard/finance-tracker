"""German freelancer tax deadlines — quarterly Einkommensteuer-Vorauszahlung, the (quarterly)
Umsatzsteuer-Voranmeldung for non-Kleinunternehmer, and the annual EÜR/Einkommensteuererklärung
filing date.

These statutory dates feed three consumers: the cashflow calendar (the ones that move cash),
the alerts feed, and a standalone ``/tax/calendar`` view. The Vorauszahlung amount reuses the
live §32a engine via :func:`backend.tax.reserve.compute_reserve` — tax math is never re-derived
here. Dates are the statutory 10th/31st and are NOT shifted for weekends/holidays (rough guide,
not tax advice).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from backend.persistence import repository
from backend.tax.reserve import compute_reserve

# ESt-Vorauszahlung: 10th of Mar/Jun/Sep/Dec. USt-Voranmeldung (quarterly filer): 10th of the
# month after each quarter. EÜR/ESt-Erklärung for a year is filed by 31 Jul of the *next* year.
_EST_VZ_MONTHS = (3, 6, 9, 12)
_UST_VA_MONTHS = (1, 4, 7, 10)
_FILING_MONTH, _FILING_DAY = 7, 31


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class TaxDeadline:
    date: date
    kind: str                  # est_vorauszahlung | ust_voranmeldung | est_erklaerung
    label: str
    amount: Decimal | None = None   # set only when the deadline moves cash (the Vorauszahlung)
    note: str | None = None


def deadlines_for_year(
    year: int, *, quarter_amount: Decimal | None, is_kleinunternehmer: bool
) -> list[TaxDeadline]:
    """Build the statutory deadlines for a single calendar ``year``."""
    out: list[TaxDeadline] = []
    for month in _EST_VZ_MONTHS:
        out.append(
            TaxDeadline(
                date=date(year, month, 10),
                kind="est_vorauszahlung",
                label="Einkommensteuer-Vorauszahlung",
                amount=_q(quarter_amount) if quarter_amount is not None else None,
                note="Geschätzte Quartalszahlung" if quarter_amount is not None else None,
            )
        )
    if not is_kleinunternehmer:
        for month in _UST_VA_MONTHS:
            out.append(
                TaxDeadline(
                    date=date(year, month, 10),
                    kind="ust_voranmeldung",
                    label="Umsatzsteuer-Voranmeldung",
                    note="Quartalsmeldung",
                )
            )
    out.append(
        TaxDeadline(
            date=date(year + 1, _FILING_MONTH, _FILING_DAY),
            kind="est_erklaerung",
            label=f"Steuererklärung {year} (EÜR) — Abgabefrist",
            note="Ohne Steuerberater",
        )
    )
    out.sort(key=lambda d: d.date)
    return out


def _quarter_amount(
    session: Session, user_id: uuid.UUID, year: int, now: datetime
) -> Decimal | None:
    """Per-quarter ESt-Vorauszahlung: the entered prepayment ÷ 4 if the user set one, else (for
    the current year only) the §32a-projected annual owed ÷ 4. None otherwise."""
    prepaid = Decimal(repository.get_tax_year_input(session, user_id, year).income_tax_prepaid)
    if prepaid > 0:
        return prepaid / Decimal(4)
    if year == now.year:
        reserve = compute_reserve(session, user_id, now)
        if reserve.projected_annual_owed > 0:
            return Decimal(reserve.projected_annual_owed) / Decimal(4)
    return None


def tax_calendar(
    session: Session, user_id: uuid.UUID, year: int, now: datetime | None = None
) -> tuple[bool, list[TaxDeadline]]:
    """(is_kleinunternehmer, deadlines) for one year — backs the ``/tax/calendar`` endpoint."""
    now = now or datetime.now(timezone.utc)
    is_klein = repository.get_business_profile(session, user_id).is_kleinunternehmer
    quarter = _quarter_amount(session, user_id, year, now)
    return is_klein, deadlines_for_year(
        year, quarter_amount=quarter, is_kleinunternehmer=is_klein
    )


def build_tax_deadlines(
    session: Session, user_id: uuid.UUID, now: datetime | None = None
) -> list[TaxDeadline]:
    """All deadlines from the current year through next year — enough to cover any cashflow
    calendar window and the alerts feed. Sorted by date."""
    now = now or datetime.now(timezone.utc)
    is_klein = repository.get_business_profile(session, user_id).is_kleinunternehmer
    out: list[TaxDeadline] = []
    for year in (now.year, now.year + 1):
        quarter = _quarter_amount(session, user_id, year, now)
        out.extend(
            deadlines_for_year(year, quarter_amount=quarter, is_kleinunternehmer=is_klein)
        )
    out.sort(key=lambda d: d.date)
    return out
