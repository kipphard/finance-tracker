"""Shared logic for savings goals (emergency fund, tax reserve) backed by a real account.

When one account backs several goals, its balance is split among them in fill-priority order
(lower ``account_priority`` first); every goal except the last is capped at its target/need and the
last goal absorbs whatever balance remains — so the same euros are never counted twice. With a
single goal this reduces to "saved = the full account balance" (the prior behaviour).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.persistence import repository

EMERGENCY_FUND = "emergency_fund"
TAX_RESERVE = "tax_reserve"
_LABELS = {EMERGENCY_FUND: "Notgroschen", TAX_RESERVE: "Steuerrücklage"}


def _ef_target(session: Session, user_id: uuid.UUID, ef) -> Decimal:
    from backend.cashflow.service import compute_summary
    if ef.target_amount is not None:
        return Decimal(ef.target_amount)
    monthly_fixed = compute_summary(session, user_id).monthly_outflow
    return Decimal(ef.target_months) * Decimal(monthly_fixed)


def _tax_owed(session: Session, user_id: uuid.UUID, now: datetime) -> Decimal:
    from backend.tax.eur import compute_eur
    return max(Decimal(0), Decimal(compute_eur(session, user_id, now.year).tax_estimate))


def goals_on_account(session: Session, user_id: uuid.UUID, account_id: uuid.UUID):
    """The savings goals backed by ``account_id`` as (priority, key), sorted by fill order."""
    goals = []
    ef = repository.get_emergency_fund(session, user_id)
    if ef.account_id == account_id:
        goals.append((ef.account_priority, EMERGENCY_FUND))
    tr = repository.get_tax_reserve(session, user_id)
    if tr.reserve_account_id == account_id:
        goals.append((tr.account_priority, TAX_RESERVE))
    goals.sort(key=lambda g: (g[0], g[1]))
    return goals


def attributed_savings(
    session: Session, user_id: uuid.UUID, account_id: uuid.UUID, now: datetime | None = None
) -> dict[str, Decimal]:
    """Split the account balance among the goals it backs, in fill-priority order."""
    now = now or datetime.now(timezone.utc)
    account = repository.get_account(session, account_id, user_id)
    if account is None:
        return {}
    remaining = Decimal(repository.account_balance(session, account))
    goals = goals_on_account(session, user_id, account_id)
    ef = repository.get_emergency_fund(session, user_id)
    out: dict[str, Decimal] = {}
    for i, (_prio, key) in enumerate(goals):
        if i == len(goals) - 1:
            take = remaining  # last goal absorbs the rest (uncapped)
        else:
            need = _ef_target(session, user_id, ef) if key == EMERGENCY_FUND \
                else _tax_owed(session, user_id, now)
            take = min(remaining, need) if need > 0 else Decimal(0)
        take = take if take > 0 else Decimal(0)
        out[key] = take
        remaining -= take
    return out


def shared_with_label(
    session: Session, user_id: uuid.UUID, account_id: uuid.UUID | None, this_key: str
) -> str | None:
    """German label of the *other* goal sharing this account, or None when not shared."""
    if account_id is None:
        return None
    others = [k for _p, k in goals_on_account(session, user_id, account_id) if k != this_key]
    return _LABELS.get(others[0]) if others else None
