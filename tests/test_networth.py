from datetime import datetime, timezone
from decimal import Decimal

from backend.connectors.manual import ManualConnector
from backend.networth.aggregator import compute_net_worth


def test_total_sums_latest_balance_per_account(db_session):
    connector = ManualConnector(db_session)
    a1 = connector.add_account(type="checking", name="A", currency="EUR")
    a2 = connector.add_account(type="cash", name="B", currency="EUR")
    db_session.commit()

    # a1 has two balances; the later ts must win.
    connector.add_balance(
        account_id=a1.id, amount=Decimal("100"), ts=datetime(2024, 1, 1, tzinfo=timezone.utc)
    )
    connector.add_balance(
        account_id=a1.id, amount=Decimal("150"), ts=datetime(2024, 2, 1, tzinfo=timezone.utc)
    )
    connector.add_balance(
        account_id=a2.id, amount=Decimal("50"), ts=datetime(2024, 1, 1, tzinfo=timezone.utc)
    )
    db_session.commit()

    net_worth = compute_net_worth(db_session)
    assert net_worth.total == Decimal("200")  # 150 + 50
    assert net_worth.by_currency["EUR"] == Decimal("200")
    assert len(net_worth.breakdown) == 2


def test_non_base_currency_excluded_from_total(db_session):
    connector = ManualConnector(db_session)
    eur = connector.add_account(type="checking", name="EUR acct", currency="EUR")
    usd = connector.add_account(type="brokerage", name="USD acct", currency="USD")
    db_session.commit()

    connector.add_balance(account_id=eur.id, amount=Decimal("100"))
    connector.add_balance(account_id=usd.id, amount=Decimal("80"))
    db_session.commit()

    net_worth = compute_net_worth(db_session)
    assert net_worth.total == Decimal("100")  # base = EUR; USD not summed in
    assert net_worth.by_currency["USD"] == Decimal("80")
    assert net_worth.by_currency["EUR"] == Decimal("100")
