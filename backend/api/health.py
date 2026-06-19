"""Liveness / readiness."""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from backend.api.deps import SessionDep

router = APIRouter(tags=["health"])


@router.get("/health")
def health(session: SessionDep) -> dict:
    try:
        session.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - report degraded rather than 500
        database = "error"
    return {"status": "ok", "database": database}
