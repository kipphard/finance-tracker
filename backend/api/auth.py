"""Auth endpoints: register, login, current user (Phase 6). Open registration."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.deps import CurrentUser, SessionDep
from backend.auth.security import create_access_token, hash_password, verify_password
from backend.persistence import repository
from backend.schemas import LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _token(user) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(str(user.id)),
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=TokenOut, status_code=201)
def register(payload: RegisterIn, session: SessionDep) -> TokenOut:
    email = payload.email.lower()
    if repository.get_user_by_email(session, email) is not None:
        raise HTTPException(status_code=409, detail="email already registered")
    user = repository.create_user(
        session, email=email, password_hash=hash_password(payload.password)
    )
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
