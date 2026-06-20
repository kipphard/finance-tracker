"""Accounting reports: monthly cashflow timeline, income/expense summary, CSV export.

All computed from the actual transaction ledger (not the recurring-cashflow plan).
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.persistence import repository


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _month_start(year: int, month: int) -> datetime:
    return datetime(year, month, 1, tzinfo=timezone.utc)


def _add_month(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


@dataclass
class MonthPoint:
    month: str
    inflow: Decimal
    outflow: Decimal
    net: Decimal


def monthly_cashflow(
    session: Session, user_id, months: int = 12, as_of: datetime | None = None
) -> list[MonthPoint]:
    as_of = as_of or _now()
    # End the window at the later of the current month or the latest transaction's month,
    # so future-dated entries (planned bills) still show up.
    end_year, end_month = as_of.year, as_of.month
    latest = repository.latest_transaction_ts(session, user_id)
    if latest is not None and (latest.year * 12 + latest.month) > (end_year * 12 + end_month):
        end_year, end_month = latest.year, latest.month

    start_year, start_month = _add_month(end_year, end_month, -(months - 1))
    start = _month_start(start_year, start_month)
    next_year, next_month = _add_month(end_year, end_month, 1)
    end = _month_start(next_year, next_month)

    buckets: dict[str, list[Decimal]] = {}
    for txn in repository.transactions_between(session, user_id, start, end):
        key = f"{txn.ts.year:04d}-{txn.ts.month:02d}"
        bucket = buckets.setdefault(key, [Decimal(0), Decimal(0)])
        if txn.amount >= 0:
            bucket[0] += txn.amount
        else:
            bucket[1] += -txn.amount

    points: list[MonthPoint] = []
    year, month = start_year, start_month
    for _ in range(months):
        key = f"{year:04d}-{month:02d}"
        inflow, outflow = buckets.get(key, [Decimal(0), Decimal(0)])
        points.append(MonthPoint(key, inflow, outflow, inflow - outflow))
        year, month = _add_month(year, month, 1)
    return points


@dataclass
class CategoryTotal:
    name: str
    kind: str | None
    total: Decimal
    count: int


@dataclass
class IncomeExpense:
    start: str
    end: str
    income: Decimal
    expense: Decimal
    net: Decimal
    by_category: list[CategoryTotal]


def income_expense(
    session: Session, user_id, start: datetime, end: datetime
) -> IncomeExpense:
    categories = {c.id: c for c in repository.list_categories(session, user_id)}
    income = Decimal(0)
    expense = Decimal(0)
    per_cat: dict = {}
    for txn in repository.transactions_between(session, user_id, start, end):
        if txn.amount >= 0:
            income += txn.amount
        else:
            expense += -txn.amount
        agg = per_cat.setdefault(txn.category_id, [Decimal(0), 0])
        agg[0] += txn.amount
        agg[1] += 1

    by_category: list[CategoryTotal] = []
    for cat_id, (total, count) in per_cat.items():
        category = categories.get(cat_id)
        by_category.append(
            CategoryTotal(
                name=category.name if category else "Uncategorized",
                kind=category.kind.value if category else None,
                total=total,
                count=count,
            )
        )
    by_category.sort(key=lambda c: abs(c.total), reverse=True)

    return IncomeExpense(
        start=start.date().isoformat(),
        end=end.date().isoformat(),
        income=income,
        expense=expense,
        net=income - expense,
        by_category=by_category,
    )


def transactions_csv(session: Session, user_id, start: datetime, end: datetime) -> str:
    categories = {c.id: c for c in repository.list_categories(session, user_id)}
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        ["date", "payee", "counterparty", "invoice_number", "category", "amount",
         "currency", "vat_rate", "description"]
    )
    for txn in repository.transactions_between(session, user_id, start, end):
        category = categories.get(txn.category_id)
        writer.writerow([
            txn.ts.date().isoformat(),
            txn.raw_payee or "",
            txn.counterparty or "",
            txn.invoice_number or "",
            category.name if category else "",
            str(txn.amount),
            txn.currency,
            str(txn.vat_rate) if txn.vat_rate is not None else "",
            txn.description or "",
        ])
    return out.getvalue()
