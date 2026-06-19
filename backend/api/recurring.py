"""Recurring / subscription detection endpoints (§4.4)."""
from __future__ import annotations

from fastapi import APIRouter

from backend.api.deps import SessionDep
from backend.categorize.recurring import detect_recurring
from backend.persistence import repository
from backend.schemas import DetectResultOut, RecurringOut

router = APIRouter(prefix="/recurring", tags=["recurring"])


@router.post("/detect", response_model=DetectResultOut)
def detect(session: SessionDep) -> DetectResultOut:
    items = detect_recurring(session)
    session.commit()
    return DetectResultOut(
        detected=len(items),
        items=[RecurringOut.model_validate(i) for i in items],
    )


@router.get("", response_model=list[RecurringOut])
def list_recurring(session: SessionDep) -> list[RecurringOut]:
    return [RecurringOut.model_validate(r) for r in repository.list_recurring(session)]
