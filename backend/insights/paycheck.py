"""Freelancer "sustainable monthly pay" — one number answering *how much can I pay myself this
month without it biting me later?*

Freelance income is lumpy; this smooths it. The headline is the trailing average monthly **net**
of real transactions (the same figure the runway/forecast use), minus the money that's already
spoken for going forward — the recommended tax-reserve set-aside and any planned-purchase savings
— and finally **capped by the liquid balance** so it never recommends paying out cash that isn't
there.

We start from net (income − expenses already in the ledger), so fixed costs are *already*
reflected and must NOT be subtracted again — ``monthly_fixed`` is reported as context only. This
is the synthesis of the existing runway + reserve + allocation views; it reuses their helpers
rather than recomputing anything.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from backend.cashflow.service import compute_summary
from backend.config import get_settings
from backend.insights.liquidity import liquid_balance
from backend.insights.service import build_forecast
from backend.persistence import repository
from backend.tax.reserve import compute_reserve


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class PaycheckLine:
    label: str
    amount: Decimal


@dataclass
class PaycheckResult:
    currency: str
    sustainable_pay: Decimal
    trailing_net: Decimal       # avg monthly net of real transactions (the base)
    trailing_income: Decimal    # avg monthly income of real transactions (context)
    monthly_fixed: Decimal      # modeled fixed costs (context — already inside trailing_net)
    tax_setaside: Decimal       # recommended monthly tax reserve (subtracted)
    goal_setaside: Decimal      # planned-purchase monthly savings (subtracted)
    liquid: Decimal             # spendable liquid balance (the cap)
    capped_by_liquid: bool
    breakdown: list[PaycheckLine] = field(default_factory=list)


def _trailing_income(session: Session, user_id: uuid.UUID, base: str) -> Decimal:
    """Average monthly income from real transactions — positive amounts only, excluding internal
    transfers and off-balance rows, averaged over the months that actually had activity. Mirrors
    the net average in :func:`build_forecast`."""
    months: set[tuple[int, int]] = set()
    total = Decimal(0)
    for txn in repository.list_transactions(session, user_id):
        if txn.currency != base or txn.excluded or txn.is_transfer:
            continue
        months.add((txn.ts.year, txn.ts.month))
        if txn.amount > 0:
            total += txn.amount
    return _q(total / len(months)) if months else Decimal("0.00")


def compute_paycheck(
    session: Session, user_id: uuid.UUID, now: datetime | None = None
) -> PaycheckResult:
    now = now or datetime.now(timezone.utc)
    base = get_settings().app_base_currency

    trailing_net = Decimal(build_forecast(session, user_id, months=1, as_of=now).monthly_net)
    trailing_income = _trailing_income(session, user_id, base)
    monthly_fixed = Decimal(compute_summary(session, user_id).monthly_outflow)
    tax_setaside = Decimal(compute_reserve(session, user_id, now).recommended_monthly)
    goal_setaside = sum(
        (Decimal(p.monthly_save) for p in repository.list_planned_purchases(session, user_id)),
        Decimal(0),
    )
    liquid, _earmarked = liquid_balance(session, user_id)

    candidate = trailing_net - tax_setaside - goal_setaside
    sustainable = max(Decimal(0), min(candidate, liquid))
    capped_by_liquid = candidate > liquid

    breakdown = [PaycheckLine(label="Avg monthly net", amount=_q(trailing_net))]
    if tax_setaside > 0:
        breakdown.append(PaycheckLine(label="− Tax reserve (per month)", amount=_q(-tax_setaside)))
    if goal_setaside > 0:
        breakdown.append(PaycheckLine(label="− Planned savings", amount=_q(-goal_setaside)))
    if capped_by_liquid:
        breakdown.append(PaycheckLine(label="capped by liquid balance", amount=_q(liquid)))

    return PaycheckResult(
        currency=base,
        sustainable_pay=_q(sustainable),
        trailing_net=_q(trailing_net),
        trailing_income=_q(trailing_income),
        monthly_fixed=_q(monthly_fixed),
        tax_setaside=_q(tax_setaside),
        goal_setaside=_q(goal_setaside),
        liquid=_q(liquid),
        capped_by_liquid=capped_by_liquid,
        breakdown=breakdown,
    )
