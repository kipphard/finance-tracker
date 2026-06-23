"""Shared FastAPI dependencies."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.auth.security import decode_token
from backend.config import get_settings
from backend.connectors.gocardless.client import GoCardlessClient
from backend.persistence import repository
from backend.persistence.database import get_session
from backend.persistence.models import User

SessionDep = Annotated[Session, Depends(get_session)]

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    subject = decode_token(credentials.credentials)
    if subject is None:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid token subject") from None
    user = repository.get_user(session, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="user not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_non_demo_user(user: CurrentUser) -> User:
    """Like CurrentUser, but 403s for demo-sandbox users — for actions that reach the outside
    world (sending invoice emails, linking real banks)."""
    if user.is_demo:
        raise HTTPException(status_code=403, detail="disabled in demo")
    return user


DemoBlockedUser = Annotated[User, Depends(get_non_demo_user)]


def get_gocardless_client() -> GoCardlessClient:
    """Build a GoCardless client from settings, or 503 if credentials are missing.

    Overridden in tests to inject a mock-transport client.
    """
    settings = get_settings()
    if not settings.gocardless_configured:
        raise HTTPException(
            status_code=503,
            detail="GoCardless is not configured (set GOCARDLESS_SECRET_ID/KEY).",
        )
    return GoCardlessClient(
        settings.gocardless_secret_id,
        settings.gocardless_secret_key,
        settings.gocardless_base_url,
    )


GoCardlessClientDep = Annotated[GoCardlessClient, Depends(get_gocardless_client)]
