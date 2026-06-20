"""Take a daily net-worth snapshot for every user (run by a systemd timer).

Idempotent: skips a user who already has a snapshot dated today, so running it more than once
(or alongside the manual button) won't create duplicate points on the trend chart.

Run: /opt/finance-tracker/.venv/bin/python -m backend.snapshot_daily
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from backend.networth.aggregator import take_snapshot
from backend.persistence import repository
from backend.persistence.database import SessionLocal
from backend.persistence.models import User


def run() -> int:
    today = datetime.now(timezone.utc).date()
    created = 0
    with SessionLocal() as session:
        users = session.execute(select(User).where(User.is_active.is_(True))).scalars().all()
        for user in users:
            already = any(s.ts.date() == today for s in repository.list_snapshots(session, user.id))
            if already:
                continue
            take_snapshot(session, user.id)  # commits
            created += 1
    return created


if __name__ == "__main__":
    n = run()
    print(f"net-worth snapshots created: {n}")
