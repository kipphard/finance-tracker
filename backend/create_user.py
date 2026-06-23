"""Create a real (non-demo) user by hand — public sign-up is disabled.

Usage:  /opt/finance-tracker/.venv/bin/python -m backend.create_user <email> <password>
"""
from __future__ import annotations

import sys

from backend.auth.security import hash_password
from backend.persistence import repository
from backend.persistence.database import SessionLocal


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: python -m backend.create_user <email> <password>")
    email, password = sys.argv[1].strip().lower(), sys.argv[2]
    with SessionLocal() as session:
        if repository.get_user_by_email(session, email) is not None:
            raise SystemExit(f"{email} already exists")
        user = repository.create_user(session, email=email, password_hash=hash_password(password))
        session.commit()
        print(f"created {email} ({user.id})")


if __name__ == "__main__":
    main()
