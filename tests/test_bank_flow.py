from decimal import Decimal

from sqlalchemy import select

from backend.connectors.gocardless.connector import BankConnector
from backend.networth.aggregator import compute_net_worth
from backend.persistence import repository
from backend.persistence.models import ConnectionStatus, Transaction
from backend.sync.engine import import_requisition_accounts, sync_connection
from gocardless_fixtures import build_mock_client


def _setup_connection(session, user):
    return repository.create_connection(
        session,
        user_id=user.id,
        connector="gocardless",
        status=ConnectionStatus.pending,
        institution_id="BANK_DE",
        requisition_id="req-1",
        reference="ref-1",
    )


def test_import_requisition_accounts(db_session, user):
    client = build_mock_client()
    connection = _setup_connection(db_session, user)
    db_session.commit()

    accounts = import_requisition_accounts(db_session, connection, client)
    assert sorted(a.name for a in accounts) == ["Girokonto", "Tagesgeld"]
    assert connection.status == ConnectionStatus.active
    assert connection.consent_expires_at is not None


def test_sync_networth_and_dedupe(db_session, user):
    client = build_mock_client()
    connection = _setup_connection(db_session, user)
    db_session.commit()
    import_requisition_accounts(db_session, connection, client)

    connector = BankConnector(db_session, user.id, client)
    result = sync_connection(db_session, connection, connector)
    assert result.accounts == 2
    assert result.balances_recorded == 2
    assert result.new_transactions == 1

    net_worth = compute_net_worth(db_session, user.id)
    assert net_worth.total == Decimal("1250.50")
    assert net_worth.by_currency["EUR"] == Decimal("1250.50")
    assert len(net_worth.breakdown) == 2

    again = sync_connection(db_session, connection, connector)
    assert again.new_transactions == 0
    txns = db_session.execute(select(Transaction)).scalars().all()
    assert len(txns) == 1


def test_purge_removes_accounts_and_balances(db_session, user):
    client = build_mock_client()
    connection = _setup_connection(db_session, user)
    db_session.commit()
    import_requisition_accounts(db_session, connection, client)
    sync_connection(db_session, connection, BankConnector(db_session, user.id, client))

    assert repository.delete_connection(db_session, connection.id, user.id) is True
    db_session.commit()
    assert compute_net_worth(db_session, user.id).total == Decimal("0")
    assert repository.list_accounts(db_session, user.id) == []
