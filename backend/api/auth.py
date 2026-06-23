"""Auth endpoints: register (gated), login, current user, and the public demo sandbox."""
from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, HTTPException, Request

from backend.api.deps import CurrentUser, SessionDep
from backend.auth.ratelimit import RateLimiter, client_ip
from backend.auth.security import create_access_token, hash_password, verify_password
from backend.config import get_settings
from backend.persistence import repository
from backend.schemas import LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

# Per-IP throttle for demo-sandbox creation (single uvicorn process → in-memory is fine).
_demo_limiter = RateLimiter(get_settings().demo_rate_per_hour, 3600.0)


def _token(user) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(str(user.id)),
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=TokenOut, status_code=201)
def register(payload: RegisterIn, session: SessionDep) -> TokenOut:
    if not get_settings().registration_enabled:
        raise HTTPException(status_code=403, detail="registration is disabled")
    email = payload.email.lower()
    if repository.get_user_by_email(session, email) is not None:
        raise HTTPException(status_code=409, detail="email already registered")
    user = repository.create_user(
        session, email=email, password_hash=hash_password(payload.password)
    )
    session.commit()
    return _token(user)


@router.post("/demo", response_model=TokenOut, status_code=201)
def demo(request: Request, session: SessionDep) -> TokenOut:
    """Public: spin up an ephemeral, fully-isolated sandbox seeded with the demo data.
    Rate-limited per IP and capped overall; cleaned up by `python -m backend.cleanup_demos`."""
    from backend.seed_demo import seed_demo_for_user  # heavy import, defer to first use

    settings = get_settings()
    if not _demo_limiter.allow(client_ip(request)):
        raise HTTPException(
            status_code=429, detail="too many demo sessions from your network — try again later"
        )
    if repository.count_demo_users(session) >= settings.demo_max_users:
        raise HTTPException(status_code=503, detail="the live demo is at capacity — try again shortly")
    user = repository.create_user(
        session,
        email=f"demo+{uuid.uuid4().hex}@demo.invalid",
        password_hash=hash_password(secrets.token_urlsafe(32)),  # unusable: login is impossible
        is_demo=True,
    )
    seed_demo_for_user(session, user.id)
    session.commit()
    return _token(user)


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, session: SessionDep) -> TokenOut:
    user = repository.get_user_by_email(session, payload.email.lower())
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="account disabled")
    return _token(user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
