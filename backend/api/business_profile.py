"""Freelance business profile (the invoice sender's own details). One per user."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.deps import CurrentUser, SessionDep
from backend.config import get_settings
from backend.invoicing.email import send_text_email
from backend.notifications import build_digest
from backend.persistence import repository
from backend.schemas import BusinessProfileOut, BusinessProfileUpdate

router = APIRouter(prefix="/business-profile", tags=["freelance"])


@router.get("", response_model=BusinessProfileOut)
def get_profile(session: SessionDep, user: CurrentUser) -> BusinessProfileOut:
    profile = repository.get_business_profile(session, user.id)
    session.commit()  # persist the default row if it was just created
    return BusinessProfileOut.model_validate(profile)


@router.patch("", response_model=BusinessProfileOut)
def update_profile(
    payload: BusinessProfileUpdate, session: SessionDep, user: CurrentUser
) -> BusinessProfileOut:
    profile = repository.get_business_profile(session, user.id)
    repository.update_business_profile(session, profile, **payload.model_dump(exclude_unset=True))
    session.commit()
    return BusinessProfileOut.model_validate(profile)


@router.post("/digest-test")
def digest_test(session: SessionDep, user: CurrentUser) -> dict:
    """Send the notification digest to yourself right now (to preview it)."""
    settings = get_settings()
    if not settings.smtp_configured:
        raise HTTPException(status_code=400, detail="email sending is not configured on the server")
    profile = repository.get_business_profile(session, user.id)
    to = profile.email or user.email
    if not to:
        raise HTTPException(status_code=400, detail="no recipient email")
    subject, body = build_digest(session, user, profile)
    try:
        send_text_email(settings, to=to, subject=subject, body=body,
                        from_addr=profile.email or settings.smtp_from or settings.smtp_user)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"failed to send: {exc}")
    return {"ok": True, "to": to}
