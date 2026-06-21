"""Send notification digests to users whose cadence is due today.

Run by a systemd timer:  /opt/finance-tracker/.venv/bin/python -m backend.send_digests
Weekly subscribers get it on Mondays; monthly on the 1st. `run(force=True)` sends to all.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from backend.config import get_settings
from backend.invoicing.email import send_text_email
from backend.notifications import build_digest
from backend.persistence.database import SessionLocal
from backend.persistence.models import BusinessProfile, User


def run(force: bool = False) -> int:
    settings = get_settings()
    if not settings.smtp_configured:
        print("SMTP not configured — no digests sent")
        return 0
    today = datetime.now(timezone.utc).date()
    sent = 0
    with SessionLocal() as session:
        for profile in session.execute(select(BusinessProfile)).scalars().all():
            cadence = profile.digest_cadence or "off"
            due = force or (cadence == "weekly" and today.weekday() == 0) or \
                (cadence == "monthly" and today.day == 1)
            if cadence == "off" or not due:
                continue
            user = session.get(User, profile.user_id)
            to = profile.email or (user.email if user else "")
            if not to:
                continue
            subject, body = build_digest(session, user, profile)
            try:
                send_text_email(settings, to=to, subject=subject, body=body,
                                from_addr=profile.email or settings.smtp_from or settings.smtp_user)
                sent += 1
            except Exception as exc:  # noqa: BLE001
                print(f"digest failed for {to}: {exc}")
    print(f"sent {sent} digests")
    return sent


if __name__ == "__main__":
    run()
