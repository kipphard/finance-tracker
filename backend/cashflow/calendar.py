"""Cashflow calendar / liquidity timeline.

A day-by-day projection of *known, dated* cash events for the next N days, and the running liquid
balance they imply. Distinct from the net-worth forecast (which extrapolates a smooth average
monthly net): this only ever shows money with a concrete date attached, so it can surface the
single tightest day and the first day the balance would go negative.

Event sources:
  * cashflow_items  — manual recurring inflows/outflows (walked by cadence)
  * recurring       — detected recurring transactions (walked by cadence)
  * invoices        — outstanding amount expected on the due date (overdue → today)
  * planned_purchases — the monthly set-aside (an outflow from spendable cash)
  * debts           — one-off obligations on their due date (overdue → today)
  * tax deadlines   — the Einkommensteuer-Vorauszahlung (the deadlines that move cash)

To avoid double-counting, recurring sources are projected from their *definitions* starting
strictly after today: ``materialize_recurring`` (run on dashboard load) has already posted the
occurrences due up to today as real transactions, and those are already in the starting balance.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from backend.cashflow.service import _advance
from backend.config import get_settings
from backend.insights.liquidity import liquid_balance
from backend.persistence import repository
from backend.persistence.models import Cadence, CashflowDirection
from backend.tax.deadlines import build_tax_deadlines

_GUARD = 500  # cap occurrences per series, mirrors materialize_recurring


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class CashEvent:
    date: date
    amount: Decimal            # signed: inflow > 0, outflow < 0
    direction: str             # "inflow" | "outflow"
    kind: str                  # cashflow_item | recurring_txn | invoice | planned_save | debt | tax
    label: str
    source_id: str | None = None


@dataclass
class CashflowDay:
    date: date
    inflow: Decimal
    outflow: Decimal
    net: Decimal
    balance: Decimal
    events: list[CashEvent] = field(default_factory=list)


@dataclass
class CashflowCalendar:
    currency: str
    start_balance: Decimal
    days: list[CashflowDay]
    min_balance: Decimal
    min_balance_date: date | None
    first_negative_date: date | None
    total_inflow: Decimal
    total_outflow: Decimal


def _to_cadence(value) -> Cadence | None:
    if isinstance(value, Cadence):
        return value
    try:
        return Cadence(str(value))
    except ValueError:
        return None


def _walk(start: date, cadence: Cadence, today: date, horizon: date):
    """Yield occurrence dates strictly after ``today`` and up to ``horizon`` (inclusive)."""
    if cadence == Cadence.one_off:
        if today < start <= horizon:
            yield start
        return
    due = start
    guard = 0
    while due <= horizon and guard < _GUARD:
        guard += 1
        if due > today:
            yield due
        due = _advance(due, cadence)


def _collect_events(
    session: Session, user_id: uuid.UUID, today: date, horizon: date, base: str
) -> list[CashEvent]:
    events: list[CashEvent] = []

    # Manual recurring inflows/outflows.
    for item in repository.list_cashflow_items(session, user_id, active_only=True):
        if item.currency != base or item.next_due is None:
            continue
        cadence = _to_cadence(item.cadence)
        if cadence is None:
            continue
        inflow = item.direction == CashflowDirection.inflow
        signed = item.amount if inflow else -item.amount
        for d in _walk(item.next_due, cadence, today, horizon):
            events.append(CashEvent(
                date=d, amount=signed,
                direction="inflow" if inflow else "outflow",
                kind="cashflow_item", label=item.name, source_id=str(item.id),
            ))

    # Detected recurring transactions (amount_est is signed).
    for rec in repository.list_recurring(session, user_id):
        if rec.next_due is None:
            continue
        cadence = _to_cadence(rec.cadence)
        if cadence is None:
            continue
        signed = Decimal(rec.amount_est)
        if signed == 0:
            continue
        for d in _walk(rec.next_due, cadence, today, horizon):
            events.append(CashEvent(
                date=d, amount=signed,
                direction="inflow" if signed > 0 else "outflow",
                kind="recurring_txn", label=rec.payee, source_id=str(rec.id),
            ))

    # Outstanding invoices: expected on the due date (overdue clamps to today).
    for inv in repository.list_invoices(session, user_id):
        if inv.status not in ("sent", "overdue") or inv.due_date is None:
            continue
        outstanding = Decimal(inv.total) - repository.invoice_paid_amount(session, user_id, inv.number)
        if outstanding <= 0:
            continue
        due = max(inv.due_date, today)
        if due > horizon:
            continue
        events.append(CashEvent(
            date=due, amount=outstanding, direction="inflow",
            kind="invoice", label=f"Invoice {inv.number}", source_id=str(inv.id),
        ))

    # Planned-purchase monthly set-asides (money leaving the spendable pool each month).
    for p in repository.list_planned_purchases(session, user_id):
        save = Decimal(p.monthly_save)
        if save <= 0:
            continue
        for d in _walk(today.replace(day=min(today.day, 28)), Cadence.monthly, today, horizon):
            events.append(CashEvent(
                date=d, amount=-save, direction="outflow",
                kind="planned_save", label=f"Save: {p.name}", source_id=str(p.id),
            ))

    # One-off debts on their due date (overdue clamps to today).
    for debt in repository.list_debts(session, user_id, unpaid_only=True):
        if debt.due_date is None:
            continue
        due = max(debt.due_date, today)
        if due > horizon:
            continue
        events.append(CashEvent(
            date=due, amount=-Decimal(debt.amount), direction="outflow",
            kind="debt", label=debt.name, source_id=str(debt.id),
        ))

    # Tax deadlines that move cash (the Einkommensteuer-Vorauszahlung).
    for dl in build_tax_deadlines(session, user_id):
        if dl.amount is None or dl.amount <= 0:
            continue
        if dl.date < today or dl.date > horizon:
            continue
        events.append(CashEvent(
            date=dl.date, amount=-Decimal(dl.amount), direction="outflow",
            kind="tax", label=dl.label, source_id=dl.kind,
        ))

    return events


def build_cashflow_calendar(
    session: Session, user_id: uuid.UUID, days: int = 90, now: datetime | None = None
) -> CashflowCalendar:
    now = now or datetime.now(timezone.utc)
    today = now.date()
    horizon = today + timedelta(days=days)
    base = get_settings().app_base_currency
    start_balance, _earmarked = liquid_balance(session, user_id)

    events = _collect_events(session, user_id, today, horizon, base)
    by_day: dict[date, list[CashEvent]] = {}
    for ev in events:
        by_day.setdefault(ev.date, []).append(ev)

    running = start_balance
    min_balance = start_balance
    min_balance_date = today
    first_negative: date | None = None
    total_in = Decimal(0)
    total_out = Decimal(0)
    out_days: list[CashflowDay] = []

    d = today
    while d <= horizon:
        day_events = by_day.get(d, [])
        inflow = sum((e.amount for e in day_events if e.amount > 0), Decimal(0))
        outflow = sum((-e.amount for e in day_events if e.amount < 0), Decimal(0))
        net = inflow - outflow
        running += net
        total_in += inflow
        total_out += outflow
        if running < min_balance:
            min_balance = running
            min_balance_date = d
        if first_negative is None and running < 0:
            first_negative = d
        out_days.append(CashflowDay(
            date=d, inflow=_q(inflow), outflow=_q(outflow), net=_q(net),
            balance=_q(running), events=day_events,
        ))
        d += timedelta(days=1)

    return CashflowCalendar(
        currency=base,
        start_balance=_q(start_balance),
        days=out_days,
        min_balance=_q(min_balance),
        min_balance_date=min_balance_date,
        first_negative_date=first_negative,
        total_inflow=_q(total_in),
        total_outflow=_q(total_out),
    )
