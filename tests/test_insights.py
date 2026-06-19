import uuid
from datetime import datetime, timezone
from decimal import Decimal

from backend.insights.service import budget_status, build_alerts, build_forecast
from backend.persistence import repository
from backend.persistence.models import Cadence, CashflowDirection, CategoryKind

AS_OF = datetime(2026, 3, 15, tzinfo=timezone.utc)


def _account(session, user):
    return repository.create_account(
        session, user_id=user.id, connector="manual", type_="cash", name="Wallet", currency="EUR"
    )


def _txn(session, user, account_id, category_id, amount, *, day=10):
    txn, _ = repository.upsert_transaction(
        session,
        user_id=user.id,
        account_id=account_id,
        ts=datetime(2026, 3, day, tzinfo=timezone.utc),
        amount=Decimal(amount),
        currency="EUR",
        hash=uuid.uuid4().hex,
        raw_payee="x",
    )
    txn.category_id = category_id
    return txn


def test_budget_status_tracks_spend(db_session, user):
    account = _account(db_session, user)
    groceries = repository.create_category(
        db_session, user_id=user.id, name="Groceries", kind=CategoryKind.expense
    )
    repository.create_budget(
        db_session, user_id=user.id, category_id=groceries.id, monthly_limit=Decimal("400")
    )
    _txn(db_session, user, account.id, groceries.id, "-100.00")
    _txn(db_session, user, account.id, groceries.id, "-200.00")
    db_session.commit()

    [status] = budget_status(db_session, user.id, as_of=AS_OF)
    assert status.spent == Decimal("300.00")
    assert status.remaining == Decimal("100.00")
    assert status.pct_used == Decimal("75.00")
    assert status.over is False


def test_budget_over_triggers_alert(db_session, user):
    account = _account(db_session, user)
    dining = repository.create_category(db_session, user_id=user.id, name="Dining", kind=CategoryKind.expense)
    repository.create_budget(db_session, user_id=user.id, category_id=dining.id, monthly_limit=Decimal("100"))
    _txn(db_session, user, account.id, dining.id, "-150.00")
    db_session.commit()

    [status] = budget_status(db_session, user.id, as_of=AS_OF)
    assert status.over is True
    alerts = build_alerts(db_session, user.id, as_of=AS_OF)
    assert any(a.kind == "budget" and a.level == "danger" for a in alerts)


def test_bill_due_soon_alert(db_session, user):
    account = _account(db_session, user)
    repository.create_recurring(
        db_session,
        user_id=user.id,
        payee="Netflix",
        amount_est=Decimal("-12.99"),
        cadence="monthly",
        next_due=datetime(2026, 3, 18, tzinfo=timezone.utc).date(),
        account_id=account.id,
    )
    db_session.commit()
    alerts = build_alerts(db_session, user.id, as_of=AS_OF)
    assert any(a.kind == "bill" and "Netflix" in a.message for a in alerts)


def test_overdue_debt_alert(db_session, user):
    repository.create_debt(
        db_session,
        user_id=user.id,
        name="Car repair",
        amount=Decimal("900"),
        due_date=datetime(2026, 3, 1, tzinfo=timezone.utc).date(),  # before AS_OF -> overdue
    )
    db_session.commit()
    alerts = build_alerts(db_session, user.id, as_of=AS_OF)
    assert any(a.kind == "debt" and a.level == "danger" for a in alerts)


def test_forecast_projection(db_session, user):
    account = _account(db_session, user)
    repository.add_balance(db_session, account_id=account.id, amount=Decimal("1000.00"))
    repository.create_cashflow_item(
        db_session,
        user_id=user.id,
        direction=CashflowDirection.inflow,
        name="Salary",
        amount=Decimal("500"),
        cadence=Cadence.monthly,
        currency="EUR",
    )
    db_session.commit()

    forecast = build_forecast(db_session, user.id, months=3, as_of=AS_OF)
    assert forecast.current_total == Decimal("1000.00")
    assert forecast.monthly_net == Decimal("500.00")
    assert len(forecast.points) == 4
    assert forecast.points[0].projected == Decimal("1000.00")
    assert forecast.points[3].projected == Decimal("2500.00")
