"""Recurring / subscription detection (§4.4).

Groups transactions by account + normalized payee + sign, and for any group with enough
occurrences at a regular monthly-ish cadence, records a `recurring` row (estimated amount,
cadence, next due date) and flags the transactions as recurring. Detection is idempotent:
it clears prior detections and rebuilds from the current transactions.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from statistics import median

from sqlalchemy.orm import Session

from backend.persistence import repository
from backend.persistence.models import Recurring

_MIN_OCCURRENCES = 3


def _normalize_payee(payee: str | None) -> str:
    return (payee or "").strip().lower()


def _cadence_from_days(days: float) -> str | None:
    if 5 <= days <= 9:
        return "weekly"
    if 12 <= days <= 16:
        return "biweekly"
    if 24 <= days <= 35:
        return "monthly"
    if 80 <= days <= 100:
        return "quarterly"
    if 350 <= days <= 380:
        return "yearly"
    return None


def detect_recurring(session: Session) -> list[Recurring]:
    transactions = repository.list_transactions(session)

    groups: dict[tuple, list] = defaultdict(list)
    for txn in transactions:
        if not txn.raw_payee:
            continue
        sign = "neg" if txn.amount < 0 else "pos"
        groups[(txn.account_id, _normalize_payee(txn.raw_payee), sign)].append(txn)

    repository.delete_all_recurring(session)

    created: list[Recurring] = []
    for (account_id, _payee, _sign), items in groups.items():
        if len(items) < _MIN_OCCURRENCES:
            continue
        items.sort(key=lambda t: t.ts)
        gaps = [
            (items[i].ts - items[i - 1].ts).days for i in range(1, len(items))
        ]
        gaps = [g for g in gaps if g > 0]
        if not gaps:
            continue
        median_gap = median(gaps)
        cadence = _cadence_from_days(median_gap)
        if cadence is None:
            continue

        amount_est = (
            sum((t.amount for t in items), Decimal(0)) / len(items)
        ).quantize(Decimal("0.01"))
        next_due = (items[-1].ts + timedelta(days=round(median_gap))).date()

        recurring = repository.create_recurring(
            session,
            payee=items[0].raw_payee,
            amount_est=amount_est,
            cadence=cadence,
            next_due=next_due,
            account_id=account_id,
        )
        for txn in items:
            txn.is_recurring = True
        created.append(recurring)

    session.flush()
    return created
