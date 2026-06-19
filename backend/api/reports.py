"""Reporting/aggregation endpoints for the dashboard + accounting (§6, freelancer)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Query, Response

from backend.api.deps import CurrentUser, SessionDep
from backend.persistence import repository
from backend.reporting import income_expense, monthly_cashflow, transactions_csv
from backend.schemas import (
    CategoryBreakdownItem,
    CategoryTotalOut,
    IncomeExpenseOut,
    MonthlyCashflowPoint,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def _range(start: date | None, end: date | None) -> tuple[datetime, datetime, date, date]:
    today = datetime.now(timezone.utc).date()
    s = start or today.replace(month=1, day=1)
    e = end or today
    start_dt = datetime(s.year, s.month, s.day, tzinfo=timezone.utc)
    end_dt = datetime(e.year, e.month, e.day, tzinfo=timezone.utc) + timedelta(days=1)
    return start_dt, end_dt, s, e


@router.get("/category-breakdown", response_model=list[CategoryBreakdownItem])
def category_breakdown(session: SessionDep, user: CurrentUser) -> list[CategoryBreakdownItem]:
    """Total transaction amount per category (signed), incl. an Uncategorized bucket."""
    categories = {c.id: c for c in repository.list_categories(session, user.id)}
    items: list[CategoryBreakdownItem] = []
    for category_id, total, count in repository.spending_by_category(session, user.id):
        category = categories.get(category_id)
        items.append(
            CategoryBreakdownItem(
                category_id=category_id,
                name=category.name if category else "Uncategorized",
                kind=category.kind if category else None,
                is_fixed=category.is_fixed if category else None,
                total=Decimal(str(total)),
                count=count,
            )
        )
    items.sort(key=lambda i: abs(i.total), reverse=True)
    return items


@router.get("/monthly-cashflow", response_model=list[MonthlyCashflowPoint])
def monthly(
    session: SessionDep, user: CurrentUser, months: int = Query(default=12, ge=1, le=36)
) -> list[MonthlyCashflowPoint]:
    return [
        MonthlyCashflowPoint(month=p.month, inflow=p.inflow, outflow=p.outflow, net=p.net)
        for p in monthly_cashflow(session, user.id, months)
    ]


@router.get("/income-expense", response_model=IncomeExpenseOut)
def income_expense_report(
    session: SessionDep,
    user: CurrentUser,
    start: date | None = None,
    end: date | None = None,
) -> IncomeExpenseOut:
    start_dt, end_dt, s, e = _range(start, end)
    report = income_expense(session, user.id, start_dt, end_dt)
    return IncomeExpenseOut(
        start=s.isoformat(),
        end=e.isoformat(),
        income=report.income,
        expense=report.expense,
        net=report.net,
        by_category=[
            CategoryTotalOut(name=c.name, kind=c.kind, total=c.total, count=c.count)
            for c in report.by_category
        ],
    )


@router.get("/transactions.csv")
def transactions_csv_export(
    session: SessionDep,
    user: CurrentUser,
    start: date | None = None,
    end: date | None = None,
) -> Response:
    start_dt, end_dt, s, e = _range(start, end)
    body = transactions_csv(session, user.id, start_dt, end_dt)
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="transactions_{s}_{e}.csv"'},
    )
