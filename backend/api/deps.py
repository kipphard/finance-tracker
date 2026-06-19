"""Shared FastAPI dependencies."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.connectors.gocardless.client import GoCardlessClient
from backend.persistence.database import get_session

SessionDep = Annotated[Session, Depends(get_session)]


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
