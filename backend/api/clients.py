"""Freelance clients (customers) + per-client time/budget summary."""
from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, HTTPException, Response

from backend.api.deps import CurrentUser, SessionDep
from backend.persistence import repository
from backend.schemas import ClientCreate, ClientOut, ClientUpdate

router = APIRouter(prefix="/clients", tags=["freelance"])


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def hours(minutes: int) -> Decimal:
    return _q(Decimal(minutes) / Decimal(60))


def client_out(session, user_id: uuid.UUID, client) -> ClientOut:
    out = ClientOut.model_validate(client)
    total_min, unbilled_min = repository.client_minutes(session, user_id, client.id)
    out.tracked_hours = hours(total_min)
    out.unbilled_hours = hours(unbilled_min)
    out.unbilled_amount = _q(out.unbilled_hours * client.hourly_rate)
    return out


@router.get("", response_model=list[ClientOut])
def list_clients(session: SessionDep, user: CurrentUser) -> list[ClientOut]:
    return [client_out(session, user.id, c) for c in repository.list_clients(session, user.id)]


@router.post("", response_model=ClientOut, status_code=201)
def create_client(payload: ClientCreate, session: SessionDep, user: CurrentUser) -> ClientOut:
    client = repository.create_client(session, user_id=user.id, **payload.model_dump())
    session.commit()
    return client_out(session, user.id, client)


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> ClientOut:
    client = repository.get_client(session, client_id, user.id)
    if client is None:
        raise HTTPException(status_code=404, detail="client not found")
    return client_out(session, user.id, client)


@router.patch("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: uuid.UUID, payload: ClientUpdate, session: SessionDep, user: CurrentUser
) -> ClientOut:
    client = repository.get_client(session, client_id, user.id)
    if client is None:
        raise HTTPException(status_code=404, detail="client not found")
    repository.update_client(session, client, **payload.model_dump(exclude_unset=True))
    session.commit()
    return client_out(session, user.id, client)


@router.delete("/{client_id}", status_code=204)
def delete_client(client_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    if not repository.delete_client(session, client_id, user.id):
        raise HTTPException(status_code=404, detail="client not found")
    session.commit()
    return Response(status_code=204)
