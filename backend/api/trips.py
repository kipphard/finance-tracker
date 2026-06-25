"""Fahrtenbuch (per-trip mileage log) endpoints. The summed km for a year flow into the EÜR."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response

from backend.api.deps import CurrentUser, SessionDep
from backend.persistence import repository
from backend.schemas import TripCreate, TripOut, TripUpdate

router = APIRouter(prefix="/trips", tags=["trips"])


def _check_client(session, client_id, user_id) -> None:
    if client_id is not None and repository.get_client(session, client_id, user_id) is None:
        raise HTTPException(status_code=400, detail="client not found")


@router.post("", response_model=TripOut, status_code=201)
def create_trip(payload: TripCreate, session: SessionDep, user: CurrentUser) -> TripOut:
    _check_client(session, payload.client_id, user.id)
    trip = repository.create_trip(session, user_id=user.id, **payload.model_dump())
    session.commit()
    return TripOut.model_validate(trip)


@router.get("", response_model=list[TripOut])
def list_trips(
    session: SessionDep, user: CurrentUser, year: int | None = None
) -> list[TripOut]:
    return [TripOut.model_validate(t) for t in repository.list_trips(session, user.id, year=year)]


@router.patch("/{trip_id}", response_model=TripOut)
def update_trip(
    trip_id: uuid.UUID, payload: TripUpdate, session: SessionDep, user: CurrentUser
) -> TripOut:
    trip = repository.get_trip(session, trip_id, user.id)
    if trip is None:
        raise HTTPException(status_code=404, detail="trip not found")
    fields = payload.model_dump(exclude_unset=True)
    if "client_id" in fields:
        _check_client(session, fields["client_id"], user.id)
    repository.update_trip(session, trip, **fields)
    session.commit()
    return TripOut.model_validate(trip)


@router.delete("/{trip_id}", status_code=204)
def delete_trip(trip_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    if not repository.delete_trip(session, trip_id, user.id):
        raise HTTPException(status_code=404, detail="trip not found")
    session.commit()
    return Response(status_code=204)
