"""Bank connection endpoints (GoCardless, Phase 1), scoped per user."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response

from backend.api.deps import CurrentUser, GoCardlessClientDep, SessionDep
from backend.config import get_settings
from backend.connectors.gocardless.connector import BankConnector
from backend.persistence import repository
from backend.persistence.models import ConnectionStatus
from backend.schemas import (
    AccountOut,
    ConnectionOut,
    FinalizeOut,
    RequisitionCreate,
    RequisitionCreateOut,
    SyncResultOut,
)
from backend.sync.engine import import_requisition_accounts, sync_connection

router = APIRouter(prefix="/banks", tags=["banks"])


@router.get("/institutions")
def list_institutions(
    client: GoCardlessClientDep, user: CurrentUser, country: str | None = None
) -> list[dict]:
    settings = get_settings()
    return client.get_institutions(country or settings.gocardless_country)


@router.post("/requisitions", response_model=RequisitionCreateOut, status_code=201)
def create_requisition(
    payload: RequisitionCreate, session: SessionDep, user: CurrentUser, client: GoCardlessClientDep
) -> RequisitionCreateOut:
    settings = get_settings()
    reference = str(uuid.uuid4())
    requisition = client.create_requisition(
        institution_id=payload.institution_id,
        redirect=settings.gocardless_redirect_url,
        reference=reference,
    )
    connection = repository.create_connection(
        session,
        user_id=user.id,
        connector=BankConnector.name,
        status=ConnectionStatus.pending,
        institution_id=payload.institution_id,
        requisition_id=requisition["id"],
        reference=reference,
    )
    session.commit()
    return RequisitionCreateOut(
        connection_id=connection.id,
        requisition_id=requisition["id"],
        link=requisition["link"],
        status=requisition.get("status", "CR"),
    )


def _finalize(session, client, connection) -> FinalizeOut:
    accounts = import_requisition_accounts(session, connection, client)
    return FinalizeOut(
        connection_id=connection.id,
        status=connection.status,
        accounts=[AccountOut.model_validate(a) for a in accounts],
    )


@router.post("/requisitions/{requisition_id}/finalize", response_model=FinalizeOut)
def finalize_requisition(
    requisition_id: str, session: SessionDep, user: CurrentUser, client: GoCardlessClientDep
) -> FinalizeOut:
    connection = repository.get_connection_by_requisition(session, user.id, requisition_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="unknown requisition")
    return _finalize(session, client, connection)


@router.get("/callback")
def consent_callback(
    session: SessionDep, user: CurrentUser, client: GoCardlessClientDep, ref: str | None = None
) -> FinalizeOut:
    """GoCardless redirects the user here after consent with ?ref=<reference>."""
    if not ref:
        raise HTTPException(status_code=400, detail="missing ref")
    connection = repository.get_connection_by_reference(session, user.id, ref)
    if connection is None:
        raise HTTPException(status_code=404, detail="unknown reference")
    return _finalize(session, client, connection)


@router.get("/connections", response_model=list[ConnectionOut])
def list_connections(session: SessionDep, user: CurrentUser) -> list[ConnectionOut]:
    return [
        ConnectionOut.model_validate(c)
        for c in repository.list_connections(session, user.id, connector=BankConnector.name)
    ]


@router.post("/connections/{connection_id}/sync", response_model=SyncResultOut)
def sync(
    connection_id: uuid.UUID, session: SessionDep, user: CurrentUser, client: GoCardlessClientDep
) -> SyncResultOut:
    connection = repository.get_connection(session, connection_id, user.id)
    if connection is None:
        raise HTTPException(status_code=404, detail="unknown connection")
    result = sync_connection(session, connection, BankConnector(session, user.id, client))
    return SyncResultOut(
        accounts=result.accounts,
        balances_recorded=result.balances_recorded,
        new_transactions=result.new_transactions,
    )


@router.delete("/connections/{connection_id}", status_code=204)
def delete_connection(
    connection_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Response:
    """Purge a connection and all of its accounts/balances/transactions (§8)."""
    if not repository.delete_connection(session, connection_id, user.id):
        raise HTTPException(status_code=404, detail="unknown connection")
    session.commit()
    return Response(status_code=204)
