"""Delete expired demo-sandbox users (and all their data) past DEMO_TTL_HOURS.

Run on the server:  /opt/finance-tracker/.venv/bin/python -m backend.cleanup_demos
Schedule it every 30 min (systemd timer, or cron — see the README).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.persistence import repository
from backend.persistence.database import SessionLocal
from backend.persistence.models import User


def _purge(session: Session, cutoff: datetime) -> int:
    ids = session.execute(
        select(User.id).where(User.is_demo.is_(True), User.created_at < cutoff)
    ).scalars().all()
    for uid in ids:
        repository.delete_user(session, uid)  # cascades all of the user's rows
    return len(ids)


def run(session: Session | None = None) -> int:
    """Delete is_demo users older than the TTL; returns how many were removed. Pass a session to
    reuse one (tests); otherwise a SessionLocal is opened and committed."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=get_settings().demo_ttl_hours)
    if session is not None:
        return _purge(session, cutoff)
    with SessionLocal() as s:
        n = _purge(s, cutoff)
        s.commit()
        return n


if __name__ == "__main__":
    print(f"deleted {run()} expired demo user(s)")
