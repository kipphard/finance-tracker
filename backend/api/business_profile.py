"""Freelance business profile (the invoice sender's own details). One per user."""
from __future__ import annotations

from fastapi import APIRouter

from backend.api.deps import CurrentUser, SessionDep
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
