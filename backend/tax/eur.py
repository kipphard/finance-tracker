"""Einnahmenüberschussrechnung (EÜR): pull a tax year's freelance income/expenses from the
ledger and compute the profit plus a rough §32a income-tax estimate.

Buckets, mirroring the sign + date-window conventions in ``backend/reporting.py``:
  * income  — positive amounts of transactions tagged with the freelance tag
  * direct  — |negative| of freelance-tagged transactions, 100% deductible, grouped by category
  * mixed   — |negative| of configured mixed-use categories (NOT tagged freelance), × business %
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


@dataclass
class EurResult:
    year: int
    tag: str
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

    tag = (tax_profile.freelance_tag or "freelance").strip().lower()
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
    direct: dict[uuid.UUID | None, list] = {}        # cat_id -> [sum, count]
    mixed: dict[uuid.UUID, list] = {}                # cat_id -> [gross_sum, count]
    line_items: list[TaxLineItem] = []

    for txn in repository.transactions_between(session, user_id, start, end):
        txn_tags = [str(t).lower() for t in (txn.tags or [])]
        cat = categories.get(txn.category_id)
        cat_name = cat.name if cat else None
        is_freelance = tag in txn_tags

        if is_freelance:
            if txn.amount >= 0:
                income += txn.amount
                line_items.append(TaxLineItem(
                    date=txn.ts.date().isoformat(), payee=txn.raw_payee or "",
                    category=cat_name, bucket="income", amount=txn.amount,
                    deductible=txn.amount, tags=txn_tags,
                ))
            else:
                agg = direct.setdefault(txn.category_id, [Decimal(0), 0])
                agg[0] += -txn.amount
                agg[1] += 1
                line_items.append(TaxLineItem(
                    date=txn.ts.date().isoformat(), payee=txn.raw_payee or "",
                    category=cat_name, bucket="direct", amount=txn.amount,
                    deductible=-txn.amount, tags=txn_tags,
                ))
        elif txn.amount < 0 and txn.category_id in mixed_rates:
            pct = mixed_rates[txn.category_id]
            agg = mixed.setdefault(txn.category_id, [Decimal(0), 0])
            agg[0] += -txn.amount
            agg[1] += 1
            line_items.append(TaxLineItem(
                date=txn.ts.date().isoformat(), payee=txn.raw_payee or "",
                category=cat_name, bucket="mixed", amount=txn.amount,
                deductible=_q(-txn.amount * pct / Decimal(100)), tags=txn_tags,
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

    for cat_id, (gross, count) in sorted(
        mixed.items(), key=lambda kv: kv[1][0], reverse=True
    ):
        cat = categories.get(cat_id)
        pct = mixed_rates[cat_id]
        deductible = gross * pct / Decimal(100)
        expense_lines.append(ExpenseLine(
            key="mixed", label=f"{cat.name if cat else 'Uncategorized'} ({_pct(pct)}%)",
            amount=_q(deductible), gross=_q(gross), percent=pct, count=count,
        ))
        expense_total += deductible

    home_office = _home_office_amount(tax_profile, year_input)
    if home_office > 0:
        label = "Homeoffice-Pauschale" if tax_profile.home_office_mode == "flat" else "Häusliches Arbeitszimmer"
        expense_lines.append(ExpenseLine(key="home_office", label=label, amount=_q(home_office)))
        expense_total += home_office

    travel = Decimal(year_input.business_km) * Decimal(tax_profile.km_rate)
    if travel > 0:
        expense_lines.append(ExpenseLine(
            key="travel",
            label=f"Reisekosten ({_pct(Decimal(year_input.business_km))} km × "
                  f"{_pct(Decimal(tax_profile.km_rate))} €)",
            amount=_q(travel),
        ))
        expense_total += travel

    profit = income - expense_total

    other = Decimal(year_input.other_taxable_income)
    t_year = tariff_year_used(year)
    tax_with = income_tax(other + profit, year)
    tax_without = income_tax(other, year)

    return EurResult(
        year=year, tag=tag, business_type=tax_profile.business_type,
        is_kleinunternehmer=business.is_kleinunternehmer,
        income=_q(income), expense_total=_q(expense_total), profit=_q(profit),
        expense_lines=expense_lines, line_items=line_items,
        other_income=_q(other), tariff_year=t_year,
        tax_with=tax_with, tax_without=tax_without, tax_estimate=tax_with - tax_without,
        home_office_mode=tax_profile.home_office_mode,
        home_office_days=year_input.home_office_days,
        business_km=Decimal(year_input.business_km), km_rate=Decimal(tax_profile.km_rate),
    )


def _pct(value: Decimal) -> str:
    """Render a Decimal without trailing zeros (50 not 50.00, 0.30 stays 0.3)."""
    v = Decimal(value).normalize()
    return format(v, "f")
