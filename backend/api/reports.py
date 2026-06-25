"""Reporting/aggregation endpoints for the dashboard + accounting (§6, freelancer)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Query, Response

from backend.api.deps import CurrentUser, SessionDep
from backend.config import get_settings
from backend.cashflow.calendar import build_cashflow_calendar
from backend.insights.advisor import compute_advisor
from backend.insights.liquidity import ILLIQUID_TYPES, liquid_balance
from backend.insights.paycheck import compute_paycheck
from backend.insights.service import build_forecast
from backend.persistence import repository
from backend.reporting import income_expense, monthly_cashflow, transactions_csv
from backend.schemas import (
    AdvisorOut,
    CashflowCalendarOut,
    CategoryBreakdownItem,
    CategoryTotalOut,
    ClientProfitOut,
    FreelanceInsightsOut,
    IncomeExpenseOut,
    MonthlyCashflowPoint,
    PaycheckOut,
    ProjectBurnOut,
    RunwayOut,
)

router = APIRouter(prefix="/reports", tags=["reports"])

# ILLIQUID_TYPES is re-exported from backend.insights.liquidity for backward compatibility.
__all__ = ["router", "ILLIQUID_TYPES"]


def _q(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"))


def _hours(minutes: int) -> Decimal:
    return _q(Decimal(minutes) / Decimal(60))


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


@router.get("/runway", response_model=RunwayOut)
def runway(session: SessionDep, user: CurrentUser) -> RunwayOut:
    """Liquid balance / monthly burn → how many months of runway you have."""
    forecast = build_forecast(session, user.id, months=1)
    monthly_net = Decimal(forecast.monthly_net)
    # Accounts earmarked for a savings goal (e.g. the tax reserve) hold money that's already
    # spoken for, so they don't count toward spendable runway.
    liquid, earmarked = liquid_balance(session, user.id)
    runway_months = _q(liquid / (-monthly_net)) if (monthly_net < 0 and liquid > 0) else None
    return RunwayOut(
        currency=get_settings().app_base_currency,
        liquid=_q(liquid), monthly_net=_q(monthly_net), runway_months=runway_months,
        earmarked=_q(earmarked),
    )


@router.get("/cashflow-calendar", response_model=CashflowCalendarOut)
def cashflow_calendar(
    session: SessionDep, user: CurrentUser, days: int = Query(default=90, ge=14, le=120)
) -> CashflowCalendarOut:
    """Day-by-day projection of dated cash events + running liquid balance for the next N days."""
    calendar = build_cashflow_calendar(session, user.id, days)
    session.commit()  # persists any default tax profile/year rows touched by the tax-deadline pass
    return CashflowCalendarOut.model_validate(calendar)


@router.get("/paycheck", response_model=PaycheckOut)
def paycheck(session: SessionDep, user: CurrentUser) -> PaycheckOut:
    """A sustainable 'pay yourself' figure: trailing net minus tax reserve and planned savings,
    capped by the liquid balance."""
    result = compute_paycheck(session, user.id)
    session.commit()  # persists any default tax reserve/profile rows created during the compute
    return PaycheckOut.model_validate(result)


@router.get("/advisor", response_model=AdvisorOut)
def advisor(session: SessionDep, user: CurrentUser) -> AdvisorOut:
    """Baseline bundle for the rate advisor + what-if scenarios (rate, runway, profit, tax)."""
    result = compute_advisor(session, user.id)
    session.commit()  # persists any default tax/business-profile rows created during the compute
    return AdvisorOut.model_validate(result)


@router.get("/freelance-insights", response_model=FreelanceInsightsOut)
def freelance_insights(session: SessionDep, user: CurrentUser) -> FreelanceInsightsOut:
    """Per-client profitability (effective €/h, utilization) + per-project budget burn-down."""
    uid = user.id
    invoiced: dict = {}
    paid: dict = {}
    for inv in repository.list_invoices(session, uid):
        invoiced[inv.client_id] = invoiced.get(inv.client_id, Decimal(0)) + Decimal(inv.total)
        if inv.status == "paid":
            paid[inv.client_id] = paid.get(inv.client_id, Decimal(0)) + Decimal(inv.total)

    clients_out = []
    for c in repository.list_clients(session, uid):
        total_min, unbilled_min = repository.client_minutes(session, uid, c.id)
        tracked = _hours(total_min)
        inv_total = invoiced.get(c.id, Decimal(0))
        clients_out.append(ClientProfitOut(
            client_id=c.id, name=c.name, tracked_hours=tracked,
            billed_hours=_hours(total_min - unbilled_min), unbilled_hours=_hours(unbilled_min),
            invoiced_total=_q(inv_total), paid_total=_q(paid.get(c.id, Decimal(0))),
            effective_rate=_q(inv_total / tracked) if tracked > 0 else Decimal(0),
        ))
    clients_out.sort(key=lambda x: x.effective_rate, reverse=True)

    projects_out = []
    for p in repository.list_projects(session, uid):
        if p.budget_hours is None:
            continue
        total_min, _ = repository.project_minutes(session, uid, p.id)
        tracked = _hours(total_min)
        budget = Decimal(p.budget_hours)
        client = repository.get_client(session, p.client_id, uid)
        projects_out.append(ProjectBurnOut(
            project_id=p.id, name=p.name, client_name=client.name if client else None,
            budget_hours=budget, tracked_hours=tracked, remaining_hours=_q(budget - tracked),
            pct=_q(tracked / budget * 100) if budget > 0 else Decimal(0),
            over_budget=tracked > budget,
        ))
    projects_out.sort(key=lambda x: x.pct, reverse=True)

    return FreelanceInsightsOut(clients=clients_out, projects=projects_out)
