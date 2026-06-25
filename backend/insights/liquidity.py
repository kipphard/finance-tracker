"""Shared definition of the spendable *liquid* balance.

Several views need the same number — the cash-runway card, the cashflow calendar's starting
balance, and the freelancer-paycheck cap — so the rule for what counts as liquid lives here once
and is reused, rather than each consumer reimplementing (and drifting from) it.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.persistence import repository

# Account types treated as not-liquid for the cash-runway / spendable calculations.
ILLIQUID_TYPES = {"brokerage", "investment", "property", "crypto", "retirement", "pension"}


def liquid_balance(session: Session, user_id: uuid.UUID) -> tuple[Decimal, Decimal]:
    """Return ``(liquid, earmarked)`` in the base currency.

    ``liquid`` is the sum of non-illiquid, non-earmarked account balances — the money actually
    available to spend. ``earmarked`` is the balance of accounts spoken-for by a savings goal
    (e.g. the tax reserve); it's reported separately and excluded from the spendable pool.
    """
    earmarked_ids = repository.earmarked_account_ids(session, user_id)
    liquid = Decimal(0)
    earmarked = Decimal(0)
    for acc in repository.list_accounts(session, user_id):
        if (acc.type or "").lower() in ILLIQUID_TYPES:
            continue
        balance = repository.account_balance(session, acc)
        if acc.id in earmarked_ids:
            earmarked += balance
            continue
        liquid += balance
    return liquid, earmarked
