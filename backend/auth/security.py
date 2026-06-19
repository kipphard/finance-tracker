"""Password hashing (bcrypt) and JWT bearer tokens (HS256)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from backend.config import get_settings

# bcrypt only uses the first 72 bytes.
_MAX = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:_MAX], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:_MAX], hashed.encode())
    except ValueError:
        return False


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        settings.effective_jwt_secret,
        algorithm="HS256",
    )


def decode_token(token: str) -> str | None:
    """Return the subject (user id) or None if the token is invalid/expired."""
    try:
        payload = jwt.decode(
            token, get_settings().effective_jwt_secret, algorithms=["HS256"]
        )
    except jwt.PyJWTError:
        return None
    return payload.get("sub")
