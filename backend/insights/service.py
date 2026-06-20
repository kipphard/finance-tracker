"""Computed views for Phase 5: budget tracking, alerts, and a simple forecast."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.networth.aggregator import compute_net_worth
from backend.persistence import repository
from backend.persistence.models import ConnectionStatus

_BILL_DUE_WINDOW_DAYS = 7
_CONSENT_WARN_DAYS = 14
_NEAR_BUDGET_PCT = Decimal("90")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def month_range(as_of: datetime) -> tuple[datetime, datetime]:
    start = as_of.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(
        month=start.month + 1
    )
    return start, end


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = (year * 12 + (month - 1)) + delta
    return idx // 12, idx % 12 + 1


# --- budgets --------------------------------------------------------------


@dataclass
class BudgetStatus:
    budget_id: str
    category_id: str
    category_name: str
    monthly_limit: Decimal
    spent: Decimal
    remaining: Decimal
    pct_used: Decimal
    over: bool
    period: str


def budget_status(
    session: Session, user_id, as_of: datetime | None = None
) -> list[BudgetStatus]:
    as_of = as_of or _now()
    start, end = month_range(as_of)
    spend = repository.category_spending_between(session, user_id, start, end)
    categories = {c.id: c for c in repository.list_categories(session, user_id)}

    statuses: list[BudgetStatus] = []
    for budget in repository.list_budgets(session, user_id):
        category = categories.get(budget.category_id)
        signed = spend.get(budget.category_id, Decimal(0))
        spent = max(Decimal(0), -signed)  # outflows count toward the budget
        limit = Decimal(budget.monthly_limit)
        remaining = limit - spent
        pct = (spent / limit * 100) if limit > 0 else Decimal(0)
        statuses.append(
            BudgetStatus(
                budget_id=str(budget.id),
                category_id=str(budget.category_id),
                category_name=category.name if category else "?",
                monthly_limit=_q(limit),
                spent=_q(spent),
                remaining=_q(remaining),
                pct_used=_q(pct),
                over=spent > limit,
                period=start.strftime("%Y-%m"),
            )
        )
    statuses.sort(key=lambda s: s.pct_used, reverse=True)
    return statuses


# --- alerts ---------------------------------------------------------------


@dataclass
class Alert:
    level: str  # "danger" | "warning" | "info"
    kind: str  # "budget" | "bill" | "consent"
    message: str


def build_alerts(session: Session, user_id, as_of: datetime | None = None) -> list[Alert]:
    as_of = as_of or _now()
    today = as_of.date()
    alerts: list[Alert] = []

    for status in budget_status(session, user_id, as_of):
        if status.over:
            alerts.append(
                Alert(
                    "danger",
                    "budget",
                    f"Over budget on {status.category_name}: "
                    f"{status.spent} / {status.monthly_limit}",
                )
            )
        elif status.pct_used >= _NEAR_BUDGET_PCT:
            alerts.append(
                Alert(
                    "warning",
                    "budget",
                    f"{status.category_name} at {status.pct_used}% of budget",
                )
            )

    for recurring in repository.list_recurring(session, user_id):
        if recurring.next_due is None:
            continue
        due: date = recurring.next_due
        days = (due - today).days
        if 0 <= days <= _BILL_DUE_WINDOW_DAYS:
            when = "today" if days == 0 else f"in {days}d"
            alerts.append(
                Alert(
                    "info",
                    "bill",
                    f"{recurring.payee} due {when} ({recurring.amount_est})",
                )
            )

    for conn in repository.list_connections(session, user_id):
        if conn.status != ConnectionStatus.active or conn.consent_expires_at is None:
            continue
        days = (conn.consent_expires_at.date() - today).days
        if 0 <= days <= _CONSENT_WARN_DAYS:
            alerts.append(
                Alert("warning", "consent", f"Bank consent expires in {days}d — re-authorize soon")
            )

    for debt in repository.list_debts(session, user_id, unpaid_only=True):
        if debt.due_date is None:
            continue
        days = (debt.due_date - today).days
        if days < 0:
            alerts.append(
                Alert("danger", "debt", f"Overdue: {debt.name} ({debt.amount}) — due {debt.due_date}")
            )
        elif days <= _BILL_DUE_WINDOW_DAYS:
            when = "today" if days == 0 else f"in {days}d"
            alerts.append(
                Alert("warning", "debt", f"{debt.name} ({debt.amount}) due {when}")
            )

    return alerts


# --- forecast -------------------------------------------------------------


@dataclass
class ForecastPoint:
    month: str
    projected: Decimal


@dataclass
class ForecastSeries:
    key: str  # "total" or an account id
    label: str  # "Total" or the account name
    points: list[ForecastPoint] = field(default_factory=list)


@dataclass
class Forecast:
    base_currency: str
    current_total: Decimal
    monthly_net: Decimal
    points: list[ForecastPoint] = field(default_factory=list)  # the total line (back-compat)
    series: list[ForecastSeries] = field(default_factory=list)


def build_forecast(
    session: Session, user_id, months: int = 6, as_of: datetime | None = None
) -> Forecast:
    as_of = as_of or _now()
    net_worth = compute_net_worth(session, user_id)
    start_total = net_worth.total

    # Project from the average net per month of the user's actual transactions
    # (averaged over the months that actually have activity).
    base = get_settings().app_base_currency
    months_with_activity: set[tuple[int, int]] = set()
    total = Decimal(0)
    for txn in repository.list_transactions(session, user_id):
        if txn.currency != base:
            continue
        total += txn.amount
        months_with_activity.add((txn.ts.year, txn.ts.month))
    monthly_net = (
        _q(total / len(months_with_activity)) if months_with_activity else Decimal("0.00")
    )

    # Each base-currency account's balance compounds at its expected annual return (0 = flat).
    holdings = [
        (a, repository.account_balance(session, a), (a.expected_return or Decimal(0)) / Decimal(100))
        for a in repository.list_accounts(session, user_id)
        if a.currency == base
    ]

    def _label(m: int) -> str:
        year, month = _add_months(as_of.year, as_of.month, m)
        return f"{year:04d}-{month:02d}"

    points: list[ForecastPoint] = []
    per_account: dict = {a.id: [] for a, _, _ in holdings}
    for m in range(0, months + 1):
        label = _label(m)
        grown = Decimal(0)
        for a, bal, rate in holdings:
            factor = Decimal(str((1.0 + float(rate)) ** (m / 12)))
            per_account[a.id].append(ForecastPoint(month=label, projected=_q(bal * factor)))
            grown += bal * factor
        # Total = growth on what you hold today + the average monthly contribution going forward.
        points.append(ForecastPoint(month=label, projected=_q(grown + monthly_net * m)))

    # One series per account that actually holds money, plus the headline Total.
    series = [ForecastSeries(key="total", label="Total", points=points)]
    for a, bal, _rate in holdings:
        if bal != 0:
            series.append(ForecastSeries(key=str(a.id), label=a.name, points=per_account[a.id]))

    return Forecast(
        base_currency=net_worth.base_currency,
        current_total=_q(start_total),
        monthly_net=_q(monthly_net),
        points=points,
        series=series,
    )
