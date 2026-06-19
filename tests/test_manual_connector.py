from datetime import date
from decimal import Decimal

from backend.connectors.manual import ManualConnector


def test_add_and_list_accounts(db_session, user):
    connector = ManualConnector(db_session, user.id)
    connector.add_account(type="checking", name="Giro", currency="EUR")
    db_session.commit()

    accounts = connector.list_accounts()
    assert len(accounts) == 1
    assert accounts[0].name == "Giro"
    assert accounts[0].connector == "manual"


def test_add_balance_and_get_latest(db_session, user):
    connector = ManualConnector(db_session, user.id)
    account = connector.add_account(type="cash", name="Wallet", currency="EUR")
    db_session.commit()

    connector.add_balance(account_id=account.id, amount=Decimal("100.50"))
    db_session.commit()

    balance = connector.get_balance(str(account.id))
    assert balance.amount == Decimal("100.50")
    assert balance.currency == "EUR"


def test_get_balance_zero_when_no_entries(db_session, user):
    connector = ManualConnector(db_session, user.id)
    account = connector.add_account(type="cash", name="Empty", currency="EUR")
    db_session.commit()

    assert connector.get_balance(str(account.id)).amount == Decimal("0")


def test_get_transactions_is_empty(db_session, user):
    connector = ManualConnector(db_session, user.id)
    account = connector.add_account(type="cash", name="X", currency="EUR")
    db_session.commit()

    assert connector.get_transactions(str(account.id), date(2020, 1, 1)) == []
