from datetime import date, datetime, timezone
from decimal import Decimal

from backend.cashflow.service import compute_summary, materialize_recurring, monthly_amount
from backend.persistence import repository
from backend.persistence.models import Cadence, CashflowDirection


def _add(session, user, direction, name, amount, cadence):
    return repository.create_cashflow_item(
        session,
        user_id=user.id,
        direction=direction,
        name=name,
        amount=Decimal(amount),
        cadence=cadence,
        currency="EUR",
    )


def test_monthly_normalization(db_session, user):
    salary = _add(db_session, user, CashflowDirection.inflow, "Salary", "3000", Cadence.monthly)
    insurance = _add(db_session, user, CashflowDirection.outflow, "Insurance", "1200", Cadence.yearly)
    groceries = _add(db_session, user, CashflowDirection.outflow, "Groceries", "50", Cadence.weekly)
    db_session.commit()

    assert monthly_amount(salary) == Decimal("3000")
    assert monthly_amount(insurance) == Decimal("100")
    assert monthly_amount(groceries).quantize(Decimal("0.01")) == Decimal("216.67")


def test_summary_inflow_outflow_net(db_session, user):
    _add(db_session, user, CashflowDirection.inflow, "Salary", "3000", Cadence.monthly)
    _add(db_session, user, CashflowDirection.outflow, "Rent", "1200", Cadence.monthly)
    _add(db_session, user, CashflowDirection.outflow, "Insurance", "1200", Cadence.yearly)
    _add(db_session, user, CashflowDirection.outflow, "Groceries", "50", Cadence.weekly)
    db_session.commit()

    summary = compute_summary(db_session, user.id)
    assert summary.monthly_inflow == Decimal("3000.00")
    assert summary.monthly_outflow == Decimal("1516.67")  # 1200 + 100 + 216.67
    assert summary.monthly_net == Decimal("1483.33")
    assert summary.item_count == 4


def test_one_off_excluded_and_inactive_excluded(db_session, user):
    _add(db_session, user, CashflowDirection.inflow, "Salary", "2000", Cadence.monthly)
    _add(db_session, user, CashflowDirection.inflow, "Bonus", "5000", Cadence.one_off)
    rent = _add(db_session, user, CashflowDirection.outflow, "Rent", "800", Cadence.monthly)
    db_session.commit()

    summary = compute_summary(db_session, user.id)
    assert summary.monthly_inflow == Decimal("2000.00")  # one-off contributes 0
    assert summary.monthly_outflow == Decimal("800.00")

    repository.update_cashflow_item(db_session, rent, active=False)
    db_session.commit()
    after = compute_summary(db_session, user.id)
    assert after.monthly_outflow == Decimal("0.00")


def test_materialize_recurring(db_session, user):
    account = repository.create_account(
        db_session, user_id=user.id, connector="manual", type_="checking", name="Biz", currency="EUR"
    )
    item = repository.create_cashflow_item(
        db_session, user_id=user.id, direction=CashflowDirection.outflow, name="Rent",
        amount=Decimal("1200"), cadence=Cadence.monthly, currency="EUR",
        account_id=account.id, next_due=date(2026, 1, 1),
    )
    db_session.commit()

    as_of = datetime(2026, 3, 15, tzinfo=timezone.utc)
    created = materialize_recurring(db_session, user.id, as_of=as_of)
    db_session.commit()
    assert created == 3  # Jan 1, Feb 1, Mar 1
    assert materialize_recurring(db_session, user.id, as_of=as_of) == 0  # idempotent

    txns = repository.list_transactions(db_session, user.id)
    assert len(txns) == 3
    assert all(t.amount == Decimal("-1200") for t in txns)  # outflow -> negative
    assert item.next_due == date(2026, 4, 1)
