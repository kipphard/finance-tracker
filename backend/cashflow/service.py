"""Cashflow math: normalize any cadence to a monthly-equivalent amount and summarize.

No FX in Phase 0/1: only items in the base currency contribute to the headline totals.
"""
from __future__ import annotations

from dataclasses import dataclass
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


def compute_summary(session: Session) -> CashflowSummary:
    base = get_settings().app_base_currency
    items = repository.list_cashflow_items(session, active_only=True)

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
