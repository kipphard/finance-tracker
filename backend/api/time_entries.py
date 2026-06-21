"""Freelance time entries: start/stop timer + manual entries."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Response

from backend.api.deps import CurrentUser, SessionDep
from backend.persistence import repository
from backend.schemas import TimeEntryCreate, TimeEntryOut, TimeEntryStart, TimeEntryUpdate

router = APIRouter(tags=["freelance"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _minutes(a: datetime, b: datetime) -> int:
    # SQLite (tests) returns naive datetimes; treat naive values as UTC so the subtraction works.
    if a.tzinfo is None:
        a = a.replace(tzinfo=timezone.utc)
    if b.tzinfo is None:
        b = b.replace(tzinfo=timezone.utc)
    return max(0, round((b - a).total_seconds() / 60))


def _ensure_client(session, user, client_id: uuid.UUID) -> None:
    if repository.get_client(session, client_id, user.id) is None:
        raise HTTPException(status_code=400, detail="unknown client")


def _ensure_project(session, user, project_id, client_id: uuid.UUID) -> None:
    """A project (if given) must belong to this user AND to the entry's client."""
    if project_id is None:
        return
    project = repository.get_project(session, project_id, user.id)
    if project is None or project.client_id != client_id:
        raise HTTPException(status_code=400, detail="unknown project for this client")


@router.get("/time-entries", response_model=list[TimeEntryOut])
def list_entries(
    session: SessionDep,
    user: CurrentUser,
    client_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    unbilled: bool = False,
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None, alias="to"),
) -> list[TimeEntryOut]:
    start = datetime.combine(from_, time(0, 0), tzinfo=timezone.utc) if from_ else None
    end = (datetime.combine(to, time(0, 0), tzinfo=timezone.utc) + timedelta(days=1)) if to else None
    return [
        TimeEntryOut.model_validate(e)
        for e in repository.list_time_entries(
            session, user.id, client_id=client_id, project_id=project_id,
            unbilled=unbilled, start=start, end=end,
        )
    ]


@router.get("/time-entries/running", response_model=TimeEntryOut | None)
def running(session: SessionDep, user: CurrentUser) -> TimeEntryOut | None:
    entry = repository.get_running_entry(session, user.id)
    return TimeEntryOut.model_validate(entry) if entry else None


@router.post("/time-entries/start", response_model=TimeEntryOut, status_code=201)
def start_timer(payload: TimeEntryStart, session: SessionDep, user: CurrentUser) -> TimeEntryOut:
    _ensure_client(session, user, payload.client_id)
    _ensure_project(session, user, payload.project_id, payload.client_id)
    open_entry = repository.get_running_entry(session, user.id)  # auto-stop any running timer
    if open_entry is not None:
        open_entry.ended_at = _now()
        open_entry.minutes = _minutes(open_entry.started_at, open_entry.ended_at)
    entry = repository.create_time_entry(
        session, user_id=user.id, client_id=payload.client_id, project_id=payload.project_id,
        started_at=_now(), ended_at=None, minutes=0, description=payload.description,
    )
    session.commit()
    return TimeEntryOut.model_validate(entry)


@router.post("/time-entries/{entry_id}/stop", response_model=TimeEntryOut)
def stop_timer(entry_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> TimeEntryOut:
    entry = repository.get_time_entry(session, entry_id, user.id)
    if entry is None:
        raise HTTPException(status_code=404, detail="time entry not found")
    if entry.ended_at is None:
        entry.ended_at = _now()
        entry.minutes = _minutes(entry.started_at, entry.ended_at)
        session.flush()
    session.commit()
    return TimeEntryOut.model_validate(entry)


@router.post("/time-entries", response_model=TimeEntryOut, status_code=201)
def create_entry(payload: TimeEntryCreate, session: SessionDep, user: CurrentUser) -> TimeEntryOut:
    _ensure_client(session, user, payload.client_id)
    _ensure_project(session, user, payload.project_id, payload.client_id)
    minutes = payload.minutes
    if minutes is None:
        minutes = _minutes(payload.started_at, payload.ended_at) if payload.ended_at else 0
    entry = repository.create_time_entry(
        session, user_id=user.id, client_id=payload.client_id, project_id=payload.project_id,
        started_at=payload.started_at, ended_at=payload.ended_at, minutes=minutes,
        description=payload.description,
    )
    session.commit()
    return TimeEntryOut.model_validate(entry)


@router.patch("/time-entries/{entry_id}", response_model=TimeEntryOut)
def update_entry(
    entry_id: uuid.UUID, payload: TimeEntryUpdate, session: SessionDep, user: CurrentUser
) -> TimeEntryOut:
    entry = repository.get_time_entry(session, entry_id, user.id)
    if entry is None:
        raise HTTPException(status_code=404, detail="time entry not found")
    data = payload.model_dump(exclude_unset=True)
    target_client = data.get("client_id") or entry.client_id
    if data.get("client_id") is not None:
        _ensure_client(session, user, data["client_id"])
    # validate a (re)assigned project against the resolved client; clear a now-mismatched one
    if "project_id" in data:
        _ensure_project(session, user, data["project_id"], target_client)
    elif "client_id" in data and entry.project_id is not None:
        data["project_id"] = None  # client changed without a new project → drop the stale one
    repository.update_time_entry(session, entry, **data)
    session.commit()
    return TimeEntryOut.model_validate(entry)


@router.delete("/time-entries/{entry_id}", status_code=204)
def delete_entry(entry_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    if not repository.delete_time_entry(session, entry_id, user.id):
        raise HTTPException(status_code=404, detail="time entry not found")
    session.commit()
    return Response(status_code=204)
