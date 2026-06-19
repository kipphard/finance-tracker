"""Net-worth total + snapshot endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from backend.api.deps import CurrentUser, SessionDep
from backend.networth.aggregator import compute_net_worth, take_snapshot
from backend.persistence import repository
from backend.schemas import NetWorthOut, SnapshotOut

router = APIRouter(prefix="/networth", tags=["networth"])


@router.get("", response_model=NetWorthOut)
def get_net_worth(session: SessionDep, user: CurrentUser) -> NetWorthOut:
    return NetWorthOut.model_validate(compute_net_worth(session, user.id))


@router.post("/snapshots", response_model=SnapshotOut, status_code=201)
def create_snapshot(session: SessionDep, user: CurrentUser) -> SnapshotOut:
    return SnapshotOut.model_validate(take_snapshot(session, user.id))


@router.get("/snapshots", response_model=list[SnapshotOut])
def list_snapshots(session: SessionDep, user: CurrentUser) -> list[SnapshotOut]:
    return [
        SnapshotOut.model_validate(s) for s in repository.list_snapshots(session, user.id)
    ]
