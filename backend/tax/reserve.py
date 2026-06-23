"""Steuerrücklage: how much income tax to keep aside for the freelance profit *so far this
year*, vs. how much is actually set aside.

"Owed" reuses the live §32a EÜR estimate (``compute_eur`` for the current calendar year) — the
incremental income tax the freelance profit adds on top of the user's other income. "Set aside"
is the balance of a designated reserve account, or a manually-entered notional amount when no
account is linked. From those we derive the shortfall, an effective reserve rate, and a
recommended monthly set-aside that keeps the jar on track to cover the full year by December.

Rough estimate, not tax advice — Soli, church tax and (for §19) VAT are out of scope.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from backend.buckets import TAX_RESERVE, attributed_savings, shared_with_label
from backend.persistence import repository
from backend.tax.eur import compute_eur


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class ReserveResult:
    year: int
    tariff_year: int
    income_ytd: Decimal          # freelance income booked so far this year
    profit_ytd: Decimal          # freelance profit so far this year (EÜR)
    owed_ytd: Decimal            # incremental income tax on that profit (§32a) = "should be aside"
    reserve: Decimal             # what's actually set aside (account balance or notional)
    gap: Decimal                 # max(0, owed − reserve): how far behind you are right now
    surplus: Decimal             # max(0, reserve − owed): buffer over what's owed so far
    funded_pct: Decimal          # reserve / owed, capped at 100
    effective_rate: Decimal      # owed / income, as a % (reserve per euro of freelance income)
    projected_annual_owed: Decimal   # owed_ytd annualised over the months elapsed
    recommended_monthly: Decimal     # set-aside/month to fully cover the year by December
    reserve_account_id: uuid.UUID | None
    reserve_account_name: str | None
    current_amount: Decimal      # the notional fallback (used when no account is linked)
    has_account: bool
    account_priority: int        # fill order when the account also backs another goal
    shared_with: str | None      # the other goal sharing the linked account, if any


def compute_reserve(
    session: Session, user_id: uuid.UUID, now: datetime | None = None
) -> ReserveResult:
    now = now or datetime.now(timezone.utc)
    year = now.year
    eur = compute_eur(session, user_id, year)
    reserve_row = repository.get_tax_reserve(session, user_id)

    # A loss lowers the tax on other income (tax_estimate < 0), but there's nothing to *reserve*
    # in that case, so the jar floors what's owed at zero.
    owed = max(Decimal(0), Decimal(eur.tax_estimate))
    income = Decimal(eur.income)
    profit = Decimal(eur.profit)

    # What's actually set aside: a linked account's (priority-attributed) balance, else notional.
    account = None
    if reserve_row.reserve_account_id is not None:
        account = repository.get_account(session, reserve_row.reserve_account_id, user_id)
    if account is not None:
        reserve = attributed_savings(
            session, user_id, reserve_row.reserve_account_id, now
        ).get(TAX_RESERVE, Decimal(0))
    else:
        reserve = Decimal(reserve_row.current_amount)

    gap = owed - reserve
    surplus = -gap if gap < 0 else Decimal(0)
    gap = gap if gap > 0 else Decimal(0)

    funded = (reserve / owed * 100) if owed > 0 else (Decimal(100) if reserve > 0 else Decimal(0))
    if funded > 100:
        funded = Decimal(100)
    effective_rate = (owed / income * 100) if income > 0 else Decimal(0)

    # Annualise what's owed so far, then spread the remaining shortfall over the rest of the year.
    months_elapsed = now.month                       # treat the current (in-progress) month as elapsed
    months_remaining = 12 - now.month + 1            # the current month through December
    projected_annual = owed * Decimal(12) / Decimal(months_elapsed) if months_elapsed else owed
    remaining_to_save = projected_annual - reserve
    recommended_monthly = (
        remaining_to_save / Decimal(months_remaining)
        if remaining_to_save > 0 and months_remaining > 0
        else Decimal(0)
    )

    return ReserveResult(
        year=year,
        tariff_year=eur.tariff_year,
        income_ytd=_q(income),
        profit_ytd=_q(profit),
        owed_ytd=_q(owed),
        reserve=_q(reserve),
        gap=_q(gap),
        surplus=_q(surplus),
        funded_pct=_q(funded),
        effective_rate=_q(effective_rate),
        projected_annual_owed=_q(projected_annual),
        recommended_monthly=_q(recommended_monthly),
        reserve_account_id=reserve_row.reserve_account_id if account is not None else None,
        reserve_account_name=account.name if account is not None else None,
        current_amount=_q(Decimal(reserve_row.current_amount)),
        has_account=account is not None,
        account_priority=reserve_row.account_priority,
        shared_with=shared_with_label(
            session, user_id,
            reserve_row.reserve_account_id if account is not None else None, TAX_RESERVE,
        ),
    )
