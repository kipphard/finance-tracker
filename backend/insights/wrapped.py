"""Money Wrapped — a Spotify-Wrapped-style year-in-review.

A read-only recap of one calendar year, derived entirely from data already in the ledger
(transactions, time entries, invoices, net-worth snapshots). No new data model; just aggregation
for a fun, shareable summary card.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.persistence import repository
from backend.reporting import income_expense


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class WrappedCategory:
    name: str
    amount: Decimal


@dataclass
class WrappedResult:
    year: int
    currency: str
    has_data: bool
    total_income: Decimal
    total_expense: Decimal
    net: Decimal
    top_categories: list[WrappedCategory] = field(default_factory=list)
    biggest_expense_payee: str | None = None
    biggest_expense_amount: Decimal = Decimal(0)
    priciest_month: str | None = None        # "YYYY-MM"
    priciest_month_amount: Decimal = Decimal(0)
    hours_worked: Decimal = Decimal(0)
    invoices_count: int = 0
    invoiced_total: Decimal = Decimal(0)
    best_client_name: str | None = None
    best_client_rate: Decimal = Decimal(0)   # effective €/h
    net_worth_delta: Decimal | None = None


def _net_worth_delta(session: Session, user_id, start: datetime, end: datetime) -> Decimal | None:
    """End-of-year net worth minus its opening value, from snapshots (None if too few)."""
    snaps = sorted(repository.list_snapshots(session, user_id), key=lambda s: s.ts)
    if not snaps:
        return None
    before = [s for s in snaps if s.ts < start]
    within = [s for s in snaps if start <= s.ts < end]
    if not within:
        return None
    opening = before[-1].total if before else within[0].total
    closing = within[-1].total
    return _q(Decimal(closing) - Decimal(opening))


def compute_wrapped(session: Session, user_id: uuid.UUID, year: int) -> WrappedResult:
    base = get_settings().app_base_currency
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)

    ie = income_expense(session, user_id, start, end)

    # Top spending categories (net-outflow categories only).
    top_categories = [
        WrappedCategory(name=c.name, amount=_q(-c.total))
        for c in ie.by_category if c.total < 0
    ][:3]

    # Biggest single expense + priciest month, in one pass over the year's transactions.
    biggest_payee: str | None = None
    biggest_amount = Decimal(0)
    by_month: dict[str, Decimal] = {}
    for txn in repository.transactions_between(session, user_id, start, end):
        if txn.amount < 0:
            spent = -txn.amount
            key = f"{txn.ts.year:04d}-{txn.ts.month:02d}"
            by_month[key] = by_month.get(key, Decimal(0)) + spent
            if spent > biggest_amount:
                biggest_amount = spent
                biggest_payee = txn.raw_payee
    priciest_month = max(by_month, key=by_month.get) if by_month else None
    priciest_amount = by_month.get(priciest_month, Decimal(0)) if priciest_month else Decimal(0)

    # Hours worked + per-client tracked minutes this year.
    minutes_by_client: dict[uuid.UUID, int] = {}
    total_minutes = 0
    for e in repository.list_time_entries(session, user_id, start=start, end=end):
        total_minutes += e.minutes
        minutes_by_client[e.client_id] = minutes_by_client.get(e.client_id, 0) + e.minutes

    # Invoices issued this year + per-client invoiced totals.
    invoices_count = 0
    invoiced_total = Decimal(0)
    invoiced_by_client: dict[uuid.UUID, Decimal] = {}
    for inv in repository.list_invoices(session, user_id):
        if inv.issue_date and start.date() <= inv.issue_date < end.date():
            invoices_count += 1
            invoiced_total += Decimal(inv.total)
            invoiced_by_client[inv.client_id] = invoiced_by_client.get(inv.client_id, Decimal(0)) + Decimal(inv.total)

    # Best client by effective €/h (needs ≥ 1 tracked hour and some invoicing).
    names = {c.id: c.name for c in repository.list_clients(session, user_id)}
    best_name: str | None = None
    best_rate = Decimal(0)
    for cid, minutes in minutes_by_client.items():
        hours = Decimal(minutes) / Decimal(60)
        invoiced = invoiced_by_client.get(cid, Decimal(0))
        if hours >= 1 and invoiced > 0:
            rate = invoiced / hours
            if rate > best_rate:
                best_rate = rate
                best_name = names.get(cid)

    has_data = bool(ie.income or ie.expense or total_minutes or invoices_count)

    return WrappedResult(
        year=year,
        currency=base,
        has_data=has_data,
        total_income=_q(ie.income),
        total_expense=_q(ie.expense),
        net=_q(ie.net),
        top_categories=top_categories,
        biggest_expense_payee=biggest_payee,
        biggest_expense_amount=_q(biggest_amount),
        priciest_month=priciest_month,
        priciest_month_amount=_q(priciest_amount),
        hours_worked=_q(Decimal(total_minutes) / Decimal(60)),
        invoices_count=invoices_count,
        invoiced_total=_q(invoiced_total),
        best_client_name=best_name,
        best_client_rate=_q(best_rate),
        net_worth_delta=_net_worth_delta(session, user_id, start, end),
    )
