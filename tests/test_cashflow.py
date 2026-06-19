from decimal import Decimal

from backend.cashflow.service import compute_summary, monthly_amount
from backend.persistence import repository
from backend.persistence.models import Cadence, CashflowDirection


def _add(session, direction, name, amount, cadence):
    return repository.create_cashflow_item(
        session,
        direction=direction,
        name=name,
        amount=Decimal(amount),
        cadence=cadence,
        currency="EUR",
    )


def test_monthly_normalization(db_session):
    salary = _add(db_session, CashflowDirection.inflow, "Salary", "3000", Cadence.monthly)
    insurance = _add(db_session, CashflowDirection.outflow, "Insurance", "1200", Cadence.yearly)
    groceries = _add(db_session, CashflowDirection.outflow, "Groceries", "50", Cadence.weekly)
    db_session.commit()

    assert monthly_amount(salary) == Decimal("3000")
    assert monthly_amount(insurance) == Decimal("100")
    # 50 * 52 / 12 = 216.666...
    assert monthly_amount(groceries).quantize(Decimal("0.01")) == Decimal("216.67")


def test_summary_inflow_outflow_net(db_session):
    _add(db_session, CashflowDirection.inflow, "Salary", "3000", Cadence.monthly)
    _add(db_session, CashflowDirection.outflow, "Rent", "1200", Cadence.monthly)
    _add(db_session, CashflowDirection.outflow, "Insurance", "1200", Cadence.yearly)
    _add(db_session, CashflowDirection.outflow, "Groceries", "50", Cadence.weekly)
    db_session.commit()

    summary = compute_summary(db_session)
    assert summary.monthly_inflow == Decimal("3000.00")
    assert summary.monthly_outflow == Decimal("1516.67")  # 1200 + 100 + 216.67
    assert summary.monthly_net == Decimal("1483.33")
    assert summary.item_count == 4


def test_one_off_excluded_and_inactive_excluded(db_session):
    _add(db_session, CashflowDirection.inflow, "Salary", "2000", Cadence.monthly)
    _add(db_session, CashflowDirection.inflow, "Bonus", "5000", Cadence.one_off)
    rent = _add(db_session, CashflowDirection.outflow, "Rent", "800", Cadence.monthly)
    db_session.commit()

    summary = compute_summary(db_session)
    assert summary.monthly_inflow == Decimal("2000.00")  # one-off contributes 0
    assert summary.monthly_outflow == Decimal("800.00")

    repository.update_cashflow_item(db_session, rent, active=False)
    db_session.commit()
    after = compute_summary(db_session)
    assert after.monthly_outflow == Decimal("0.00")
