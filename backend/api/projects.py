"""Freelance projects under a client + per-project time/budget summary."""
from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, HTTPException, Response

from backend.api.deps import CurrentUser, SessionDep
from backend.persistence import repository
from backend.schemas import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["freelance"])


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _hours(minutes: int) -> Decimal:
    return _q(Decimal(minutes) / Decimal(60))


def project_out(session, user_id: uuid.UUID, project) -> ProjectOut:
    out = ProjectOut.model_validate(project)
    client = repository.get_client(session, project.client_id, user_id)
    effective = project.hourly_rate if project.hourly_rate is not None else (
        client.hourly_rate if client else Decimal(0)
    )
    out.effective_rate = _q(effective)
    total_min, unbilled_min = repository.project_minutes(session, user_id, project.id)
    out.tracked_hours = _hours(total_min)
    out.unbilled_hours = _hours(unbilled_min)
    out.unbilled_amount = _q(out.unbilled_hours * effective)
    return out


def _ensure_client(session, user, client_id: uuid.UUID) -> None:
    if repository.get_client(session, client_id, user.id) is None:
        raise HTTPException(status_code=400, detail="unknown client")


@router.get("", response_model=list[ProjectOut])
def list_projects(
    session: SessionDep, user: CurrentUser, client_id: uuid.UUID | None = None
) -> list[ProjectOut]:
    return [
        project_out(session, user.id, p)
        for p in repository.list_projects(session, user.id, client_id=client_id)
    ]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate, session: SessionDep, user: CurrentUser) -> ProjectOut:
    _ensure_client(session, user, payload.client_id)
    project = repository.create_project(session, user_id=user.id, **payload.model_dump())
    session.commit()
    return project_out(session, user.id, project)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> ProjectOut:
    project = repository.get_project(session, project_id, user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project_out(session, user.id, project)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: uuid.UUID, payload: ProjectUpdate, session: SessionDep, user: CurrentUser
) -> ProjectOut:
    project = repository.get_project(session, project_id, user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    repository.update_project(session, project, **payload.model_dump(exclude_unset=True))
    session.commit()
    return project_out(session, user.id, project)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    if not repository.delete_project(session, project_id, user.id):
        raise HTTPException(status_code=404, detail="project not found")
    session.commit()
    return Response(status_code=204)
