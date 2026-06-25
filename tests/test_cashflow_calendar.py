"""Cashflow calendar / liquidity timeline (engine + endpoint)."""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.cashflow.calendar import build_cashflow_calendar
from backend.insights.liquidity import liquid_balance
from backend.persistence import repository
from backend.persistence.models import Cadence, CashflowDirection, Client, Invoice

TODAY = datetime.now(timezone.utc).date()
TS = f"{datetime.now(timezone.utc).strftime('%Y-%m-01')}T00:00:00Z"


def _account(session, user, type_="checking"):
    return repository.create_account(
        session, user_id=user.id, connector="manual", type_=type_, name="Giro", currency="EUR"
    )


def _txn(session, user, account_id, amount, *, days_ago=1):
    repository.upsert_transaction(
        session, user_id=user.id, account_id=account_id,
        ts=datetime.now(timezone.utc) - timedelta(days=days_ago),
        amount=Decimal(amount), currency="EUR", hash=uuid.uuid4().hex, raw_payee="x",
    )


def test_start_balance_matches_liquid(db_session, user):
    acc = _account(db_session, user)
    _txn(db_session, user, acc.id, "1000")
    cal = build_cashflow_calendar(db_session, user.id, days=60)
    liquid, _ = liquid_balance(db_session, user.id)
    assert cal.start_balance == liquid == Decimal("1000.00")


def test_flags_negative_day(db_session, user):
    acc = _account(db_session, user)
    _txn(db_session, user, acc.id, "100")
    repository.create_cashflow_item(
        db_session, user_id=user.id, direction=CashflowDirection.outflow,
        name="Big bill", amount=Decimal("500"), cadence=Cadence.one_off, currency="EUR",
        next_due=TODAY + timedelta(days=10),
    )
    cal = build_cashflow_calendar(db_session, user.id, days=30)
    assert cal.first_negative_date == TODAY + timedelta(days=10)
    assert cal.min_balance == Decimal("-400.00")
    assert cal.total_outflow == Decimal("500.00")


def test_monthly_cadence_expands(db_session, user):
    acc = _account(db_session, user)
    _txn(db_session, user, acc.id, "5000")
    repository.create_cashflow_item(
        db_session, user_id=user.id, direction=CashflowDirection.inflow,
        name="Salary", amount=Decimal("1000"), cadence=Cadence.monthly, currency="EUR",
        next_due=TODAY + timedelta(days=1),
    )
    cal = build_cashflow_calendar(db_session, user.id, days=100)
    salary = [e for d in cal.days for e in d.events if e.label == "Salary"]
    assert len(salary) >= 3  # ~one per month inside the window
    assert all(e.amount == Decimal("1000") for e in salary)
    assert cal.total_inflow == Decimal(len(salary) * 1000)


def test_outstanding_invoice_is_inflow_paid_contributes_zero(db_session, user):
    acc = _account(db_session, user)
    _txn(db_session, user, acc.id, "100")
    cl = Client(user_id=user.id, name="Co")
    db_session.add(cl)
    db_session.flush()
    db_session.add(Invoice(
        user_id=user.id, client_id=cl.id, number="INV-1", status="sent",
        total=Decimal("900"), due_date=TODAY + timedelta(days=20),
    ))
    # A fully-paid invoice contributes nothing (outstanding == 0).
    paid = Invoice(
        user_id=user.id, client_id=cl.id, number="INV-2", status="sent",
        total=Decimal("300"), due_date=TODAY + timedelta(days=15),
    )
    db_session.add(paid)
    db_session.flush()
    repository.upsert_transaction(
        db_session, user_id=user.id, account_id=acc.id,
        ts=datetime.now(timezone.utc) - timedelta(days=1), amount=Decimal("300"),
        currency="EUR", hash=uuid.uuid4().hex, raw_payee="paid", invoice_number="INV-2",
    )
    cal = build_cashflow_calendar(db_session, user.id, days=60)
    inv_events = [e for d in cal.days for e in d.events if e.kind == "invoice"]
    assert len(inv_events) == 1 and inv_events[0].amount == Decimal("900")


def test_endpoint_window_and_validation(client):
    acc = client.post("/api/accounts", json={"type": "checking", "name": "Giro"}).json()["id"]
    client.post(f"/api/accounts/{acc}/transactions",
                json={"ts": TS, "amount": "500", "raw_payee": "x"})
    r = client.get("/api/reports/cashflow-calendar", params={"days": 60})
    assert r.status_code == 200
    body = r.json()
    assert Decimal(str(body["start_balance"])) == Decimal("500.00")
    assert len(body["days"]) == 61  # today .. today+60 inclusive
    assert client.get("/api/reports/cashflow-calendar", params={"days": 200}).status_code == 422
