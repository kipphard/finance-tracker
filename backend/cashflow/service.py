"""Cashflow math: normalize any cadence to a monthly-equivalent amount and summarize.

No FX in Phase 0/1: only items in the base currency contribute to the headline totals.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.persistence import repository
from backend.persistence.models import Cadence, CashflowDirection, CashflowItem

# Multiplier converting one occurrence at a given cadence into a monthly-equivalent amount.
_MONTHLY_FACTORS: dict[Cadence, Decimal] = {
    Cadence.one_off: Decimal(0),  # not part of the recurring monthly figure
    Cadence.weekly: Decimal(52) / Decimal(12),
    Cadence.biweekly: Decimal(26) / Decimal(12),
    Cadence.monthly: Decimal(1),
    Cadence.quarterly: Decimal(1) / Decimal(3),
    Cadence.yearly: Decimal(1) / Decimal(12),
}


def monthly_amount(item: CashflowItem) -> Decimal:
    return item.amount * _MONTHLY_FACTORS[item.cadence]


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class CashflowSummary:
    currency: str
    monthly_inflow: Decimal
    monthly_outflow: Decimal
    monthly_net: Decimal
    item_count: int


def compute_summary(session: Session, user_id) -> CashflowSummary:
    base = get_settings().app_base_currency
    items = repository.list_cashflow_items(session, user_id, active_only=True)

    total_in = Decimal(0)
    total_out = Decimal(0)
    counted = 0
    for item in items:
        if item.currency != base:
            continue  # no FX conversion
        counted += 1
        amount = monthly_amount(item)
        if item.direction == CashflowDirection.inflow:
            total_in += amount
        else:
            total_out += amount

    return CashflowSummary(
        currency=base,
        monthly_inflow=_q(total_in),
        monthly_outflow=_q(total_out),
        monthly_net=_q(total_in - total_out),
        item_count=counted,
    )


# --- recurring transactions (auto-post on a cadence) ----------------------


def _add_months_date(d: date, n: int) -> date:
    idx = d.year * 12 + (d.month - 1) + n
    year, month = idx // 12, idx % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _advance(d: date, cadence: Cadence) -> date:
    if cadence == Cadence.weekly:
        return d + timedelta(days=7)
    if cadence == Cadence.biweekly:
        return d + timedelta(days=14)
    if cadence == Cadence.monthly:
        return _add_months_date(d, 1)
    if cadence == Cadence.quarterly:
        return _add_months_date(d, 3)
    if cadence == Cadence.yearly:
        return _add_months_date(d, 12)
    return d


def materialize_recurring(session: Session, user_id, as_of: datetime | None = None) -> int:
    """Create the actual transactions due for each recurring template (a cashflow item with a
    target account, cadence and next_due). Catches up missed periods; idempotent."""
    today = (as_of or datetime.now(timezone.utc)).date()
    created = 0
    for item in repository.list_cashflow_items(session, user_id, active_only=True):
        if item.account_id is None or item.cadence == Cadence.one_off or item.next_due is None:
            continue
        due = item.next_due
        guard = 0
        while due <= today and guard < 500:
            guard += 1
            ts = datetime(due.year, due.month, due.day, tzinfo=timezone.utc)
            amount = item.amount if item.direction == CashflowDirection.inflow else -item.amount
            txn, was_created = repository.upsert_transaction(
                session,
                user_id=user_id,
                account_id=item.account_id,
                ts=ts,
                amount=amount,
                currency=item.currency,
                hash=f"cf:{item.id}:{due.isoformat()}",
                raw_payee=item.name,
            )
            if was_created:
                if item.category_id:
                    txn.category_id = item.category_id
                created += 1
            due = _advance(due, item.cadence)
        item.next_due = due
    session.flush()
    return created
