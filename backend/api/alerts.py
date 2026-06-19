"""Computed alerts feed (over-budget, bills due soon, consent expiring) — §5 polish."""
from __future__ import annotations

from fastapi import APIRouter

from backend.api.deps import CurrentUser, SessionDep
from backend.insights.service import build_alerts
from backend.schemas import AlertOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(session: SessionDep, user: CurrentUser) -> list[AlertOut]:
    return [AlertOut(**vars(a)) for a in build_alerts(session, user.id)]
