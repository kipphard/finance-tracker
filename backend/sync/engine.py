"""Sync engine (§4.2).

Two operations for a GoCardless connection:
- `import_requisition_accounts`: after the user consents, create local Account rows for each
  linked bank account and mark the connection active (with a 90-day consent window).
- `sync_connection`: pull the latest balance (a new time-series point) and transactions
  (idempotent upsert deduped by hash) for every account on a connection.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.connectors.gocardless.client import GoCardlessClient
from backend.connectors.gocardless.connector import BankConnector
from backend.persistence import repository
from backend.persistence.models import Account, Connection, ConnectionStatus

# Default consent lifetime when GoCardless doesn't tell us otherwise (PSD2 ~90 days).
_CONSENT_DAYS = 90
# How far back to request transactions on a sync.
_DEFAULT_HISTORY_DAYS = 90


@dataclass
class SyncResult:
    accounts: int
    balances_recorded: int
    new_transactions: int


def import_requisition_accounts(
    session: Session, connection: Connection, client: GoCardlessClient
) -> list[Account]:
    requisition = client.get_requisition(connection.requisition_id)
    created: list[Account] = []
    for external_id in requisition.get("accounts", []):
        if repository.get_account_by_external_id(session, external_id) is not None:
            continue
        details = client.get_account_details(external_id).get("account", {})
        name = (
            details.get("name")
            or details.get("ownerName")
            or details.get("product")
            or f"Account {external_id[:8]}"
        )
        account = repository.create_account(
            session,
            connector=BankConnector.name,
            type_="bank",
            name=name,
            currency=details.get("currency") or "EUR",
            institution=connection.institution_id,
            connection_id=connection.id,
            external_id=external_id,
        )
        created.append(account)

    connection.status = ConnectionStatus.active
    if connection.consent_expires_at is None:
        connection.consent_expires_at = datetime.now(timezone.utc) + timedelta(
            days=_CONSENT_DAYS
        )
    session.commit()
    return created


def sync_connection(
    session: Session,
    connection: Connection,
    connector: BankConnector,
    *,
    since: date | None = None,
) -> SyncResult:
    if since is None:
        since = (datetime.now(timezone.utc) - timedelta(days=_DEFAULT_HISTORY_DAYS)).date()

    accounts = repository.list_accounts_for_connection(session, connection.id)
    balances_recorded = 0
    new_transactions = 0

    for account in accounts:
        balance = connector.get_balance(str(account.id))
        repository.add_balance(
            session, account_id=account.id, amount=balance.amount, ts=balance.ts
        )
        balances_recorded += 1

        for txn in connector.get_transactions(str(account.id), since):
            _, created = repository.upsert_transaction(
                session,
                account_id=account.id,
                ts=txn.ts,
                amount=txn.amount,
                currency=txn.currency,
                hash=txn.hash,
                raw_payee=txn.raw_payee,
                description=txn.description,
            )
            if created:
                new_transactions += 1

    session.commit()
    return SyncResult(
        accounts=len(accounts),
        balances_recorded=balances_recorded,
        new_transactions=new_transactions,
    )
