"""Account self-service: GDPR data export and account deletion (Phase 6 / §9)."""
from __future__ import annotations

from fastapi import APIRouter, Response

from backend.api.deps import CurrentUser, SessionDep
from backend.persistence import repository
from backend.schemas import (
    AccountOut,
    BalanceOut,
    BudgetOut,
    CashflowItemOut,
    CategoryOut,
    ConnectionOut,
    RecurringOut,
    RuleOut,
    SnapshotOut,
    TransactionOut,
    UserOut,
)

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/export")
def export_data(session: SessionDep, user: CurrentUser) -> dict:
    """Export all of the current user's data as JSON (right to data portability).

    Bank tokens are intentionally excluded (ConnectionOut carries no token fields).
    """
    accounts = repository.list_accounts(session, user.id)
    balances = []
    for account in accounts:
        balances.extend(repository.list_balances(session, account.id))

    def dump(models, schema):
        return [schema.model_validate(m).model_dump(mode="json") for m in models]

    return {
        "user": UserOut.model_validate(user).model_dump(mode="json"),
        "accounts": dump(accounts, AccountOut),
        "balances": dump(balances, BalanceOut),
        "transactions": dump(repository.list_transactions(session, user.id), TransactionOut),
        "categories": dump(repository.list_categories(session, user.id), CategoryOut),
        "rules": dump(repository.list_rules(session, user.id), RuleOut),
        "recurring": dump(repository.list_recurring(session, user.id), RecurringOut),
        "cashflow_items": dump(repository.list_cashflow_items(session, user.id), CashflowItemOut),
        "budgets": dump(repository.list_budgets(session, user.id), BudgetOut),
        "snapshots": dump(repository.list_snapshots(session, user.id), SnapshotOut),
        "connections": dump(repository.list_connections(session, user.id), ConnectionOut),
    }


@router.delete("", status_code=204)
def delete_account(session: SessionDep, user: CurrentUser) -> Response:
    """Right to erasure: permanently delete the user and all of their data."""
    repository.delete_user(session, user.id)
    session.commit()
    return Response(status_code=204)
