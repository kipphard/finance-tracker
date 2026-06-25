"""Einnahmenüberschussrechnung (EÜR): pull a tax year's freelance income/expenses from the
ledger and compute the profit plus a rough §32a income-tax estimate.

Buckets, mirroring the sign + date-window conventions in ``backend/reporting.py``:
  * income  — positive amounts of transactions flagged as business
  * direct  — |negative| of business-flagged transactions, 100% deductible, grouped by category
  * mixed   — per-transaction deductible %, or |negative| of configured mixed-use categories
              (for non-business transactions), × business %
  * allowances — Homeoffice-Pauschale / Arbeitszimmer and business-travel (km × rate)

``excluded`` (off-balance) records ARE counted — they're the bookkeeping rows kept for taxes.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from backend.persistence import repository
from backend.tax.tariff import income_tax, tariff_year_used

HOME_OFFICE_DAILY = Decimal(6)          # €/day Homeoffice-Pauschale (Tagespauschale)
HOME_OFFICE_CAP = Decimal(1260)         # annual cap (also the Arbeitszimmer Jahrespauschale)


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class ExpenseLine:
    key: str                       # direct | mixed | home_office | travel
    label: str
    amount: Decimal                # deductible amount
    gross: Decimal | None = None   # full cost before applying the % (mixed-use only)
    percent: Decimal | None = None
    count: int = 0


@dataclass
class TaxLineItem:
    date: str
    payee: str
    category: str | None
    bucket: str                    # income | direct | mixed
    amount: Decimal                # the ledger amount (signed)
    deductible: Decimal           # counted toward the EÜR (income amount, or deductible expense)
    tags: list[str]
    percent: Decimal | None = None  # business share applied (mixed bucket only)


@dataclass
class EurResult:
    year: int
    business_type: str
    is_kleinunternehmer: bool
    income: Decimal
    expense_total: Decimal
    profit: Decimal
    expense_lines: list[ExpenseLine] = field(default_factory=list)
    line_items: list[TaxLineItem] = field(default_factory=list)
    # §32a estimate
    other_income: Decimal = Decimal(0)
    tariff_year: int = 0
    tax_with: Decimal = Decimal(0)
    tax_without: Decimal = Decimal(0)
    tax_estimate: Decimal = Decimal(0)
    # Full-year Erstattung/Nachzahlung: the marginal §32a tax the profit adds, minus business
    # Einkommensteuer-Vorauszahlungen (the withheld Lohnsteuer is assumed to settle the salary's
    # tax). refund_or_owed > 0 = Nachzahlung owed; < 0 = Erstattung (refund).
    withheld_lohnsteuer: Decimal = Decimal(0)
    income_tax_prepaid: Decimal = Decimal(0)
    refund_or_owed: Decimal = Decimal(0)
    # questionnaire echo (for display + the ELSTER prompt)
    home_office_mode: str = "none"
    home_office_days: int = 0
    business_km: Decimal = Decimal(0)
    km_rate: Decimal = Decimal(0)


def _home_office_amount(tax_profile, year_input) -> Decimal:
    mode = tax_profile.home_office_mode
    if mode == "flat":
        return min(Decimal(year_input.home_office_days) * HOME_OFFICE_DAILY, HOME_OFFICE_CAP)
    if mode == "room":
        if tax_profile.room_use_pauschale:
            return HOME_OFFICE_CAP
        room = tax_profile.room_sqm
        total = tax_profile.home_total_sqm
        if room and total and Decimal(total) > 0:
            return Decimal(tax_profile.home_annual_cost) * (Decimal(room) / Decimal(total))
    return Decimal(0)


def compute_eur(session: Session, user_id: uuid.UUID, year: int) -> EurResult:
    business = repository.get_business_profile(session, user_id)
    tax_profile = repository.get_tax_profile(session, user_id)
    year_input = repository.get_tax_year_input(session, user_id, year)
    categories = {c.id: c for c in repository.list_categories(session, user_id)}

    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)

    # Mixed-use category percentages, keyed by category UUID.
    mixed_rates: dict[uuid.UUID, Decimal] = {}
    for cat_key, pct in (tax_profile.mixed_use_rates or {}).items():
        try:
            mixed_rates[uuid.UUID(str(cat_key))] = Decimal(str(pct))
        except (ValueError, AttributeError):
            continue

    income = Decimal(0)
    direct: dict[uuid.UUID | None, list] = {}        # cat_id -> [deductible_sum, count]
    mixed: dict[uuid.UUID | None, list] = {}         # cat_id -> [gross_sum, deductible_sum, count]
    line_items: list[TaxLineItem] = []

    def _add_mixed(cat_id, gross: Decimal, deductible: Decimal) -> None:
        agg = mixed.setdefault(cat_id, [Decimal(0), Decimal(0), 0])
        agg[0] += gross
        agg[1] += deductible
        agg[2] += 1

    for txn in repository.transactions_between(session, user_id, start, end):
        txn_tags = [str(t).lower() for t in (txn.tags or [])]
        cat = categories.get(txn.category_id)
        cat_name = cat.name if cat else None
        is_business = bool(txn.is_business)
        date_iso = txn.ts.date().isoformat()
        payee = txn.raw_payee or ""

        # Income: positive amounts flagged as business.
        if txn.amount >= 0:
            if is_business:
                income += txn.amount
                line_items.append(TaxLineItem(
                    date=date_iso, payee=payee, category=cat_name, bucket="income",
                    amount=txn.amount, deductible=txn.amount, tags=txn_tags,
                ))
            continue

        # Expense. Precedence: an explicit per-transaction % wins, then the business flag (100%),
        # then the category's mixed-use rate; anything else is not deductible.
        gross = -txn.amount
        if txn.deductible_pct is not None:
            pct = Decimal(txn.deductible_pct)
            deductible = _q(gross * pct / Decimal(100))
            _add_mixed(txn.category_id, gross, deductible)
            line_items.append(TaxLineItem(
                date=date_iso, payee=payee, category=cat_name, bucket="mixed",
                amount=txn.amount, deductible=deductible, percent=pct, tags=txn_tags,
            ))
        elif is_business:
            agg = direct.setdefault(txn.category_id, [Decimal(0), 0])
            agg[0] += gross
            agg[1] += 1
            line_items.append(TaxLineItem(
                date=date_iso, payee=payee, category=cat_name, bucket="direct",
                amount=txn.amount, deductible=gross, tags=txn_tags,
            ))
        elif txn.category_id in mixed_rates:
            pct = mixed_rates[txn.category_id]
            deductible = _q(gross * pct / Decimal(100))
            _add_mixed(txn.category_id, gross, deductible)
            line_items.append(TaxLineItem(
                date=date_iso, payee=payee, category=cat_name, bucket="mixed",
                amount=txn.amount, deductible=deductible, percent=pct, tags=txn_tags,
            ))

    expense_lines: list[ExpenseLine] = []
    expense_total = Decimal(0)

    for cat_id, (total, count) in sorted(
        direct.items(), key=lambda kv: kv[1][0], reverse=True
    ):
        cat = categories.get(cat_id)
        expense_lines.append(ExpenseLine(
            key="direct", label=cat.name if cat else "Uncategorized",
            amount=_q(total), count=count,
        ))
        expense_total += total

    for cat_id, (gross, deductible, count) in sorted(
        mixed.items(), key=lambda kv: kv[1][1], reverse=True
    ):
        cat = categories.get(cat_id)
        # Blended share across the category's transactions; equals the single rate when uniform,
        # or reflects the mix once individual transactions carry their own % override.
        blended = (deductible / gross * Decimal(100)) if gross > 0 else Decimal(0)
        blended = _q(blended)
        expense_lines.append(ExpenseLine(
            key="mixed", label=f"{cat.name if cat else 'Uncategorized'} ({_pct(blended)}%)",
            amount=_q(deductible), gross=_q(gross), percent=blended, count=count,
        ))
        expense_total += deductible

    home_office = _home_office_amount(tax_profile, year_input)
    if home_office > 0:
        label = "Homeoffice-Pauschale" if tax_profile.home_office_mode == "flat" else "Häusliches Arbeitszimmer"
        expense_lines.append(ExpenseLine(key="home_office", label=label, amount=_q(home_office)))
        expense_total += home_office

    # Business km: the summed Fahrtenbuch trips for the year take precedence; the single manual
    # business_km figure is the fallback when no trips are logged.
    trips_km = repository.trips_km_for_year(session, user_id, year)
    business_km = trips_km if trips_km > 0 else Decimal(year_input.business_km)
    travel = business_km * Decimal(tax_profile.km_rate)
    if travel > 0:
        expense_lines.append(ExpenseLine(
            key="travel",
            label=f"Reisekosten ({_pct(business_km)} km × {_pct(Decimal(tax_profile.km_rate))} €)",
            amount=_q(travel),
        ))
        expense_total += travel

    profit = income - expense_total

    other = Decimal(year_input.other_taxable_income)
    t_year = tariff_year_used(year)
    tax_with = income_tax(other + profit, year)
    tax_without = income_tax(other, year)
    tax_estimate = tax_with - tax_without  # marginal §32a tax the freelance profit adds

    # Full-year Erstattung/Nachzahlung. The withheld Lohnsteuer is treated as having already
    # settled the income tax on the salary (other income) — that is precisely what the monthly
    # Lohnsteuerabzug does — so the only amount still open at assessment is the marginal §32a tax
    # on the freelance profit, less any business Einkommensteuer-Vorauszahlungen.
    #
    # We deliberately do NOT compute `income_tax(gross_salary) − withheld`: the "Bruttoarbeitslohn"
    # input is gross, not the zu versteuerndes Einkommen (Werbungskosten/Arbeitnehmer-Pauschbetrag
    # and especially Vorsorgeaufwendungen are not modelled), and only the Grundtarif is used (no
    # Ehegatten-Splitting). Running §32a on gross overstated the salary's tax and produced a large
    # phantom Nachzahlung for employees whose salary is already correctly withheld.
    withheld = Decimal(year_input.withheld_lohnsteuer)
    prepaid = Decimal(year_input.income_tax_prepaid)
    refund_or_owed = tax_estimate - prepaid

    return EurResult(
        year=year, business_type=tax_profile.business_type,
        is_kleinunternehmer=business.is_kleinunternehmer,
        income=_q(income), expense_total=_q(expense_total), profit=_q(profit),
        expense_lines=expense_lines, line_items=line_items,
        other_income=_q(other), tariff_year=t_year,
        tax_with=tax_with, tax_without=tax_without, tax_estimate=tax_estimate,
        withheld_lohnsteuer=_q(withheld), income_tax_prepaid=_q(prepaid),
        refund_or_owed=_q(refund_or_owed),
        home_office_mode=tax_profile.home_office_mode,
        home_office_days=year_input.home_office_days,
        business_km=Decimal(year_input.business_km), km_rate=Decimal(tax_profile.km_rate),
    )


def _pct(value: Decimal) -> str:
    """Render a Decimal without trailing zeros (50 not 50.00, 0.30 stays 0.3)."""
    v = Decimal(value).normalize()
    return format(v, "f")
