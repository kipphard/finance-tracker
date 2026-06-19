"""Fernet-based encryption for secrets stored at rest (§8 of the plan).

`EncryptedString` is a SQLAlchemy column type that transparently encrypts on write and
decrypts on read, so access tokens are never persisted in plaintext. The mechanism is in
place and tested now even though no real bank token is stored until Phase 1.
"""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from backend.config import get_settings


@lru_cache
def get_fernet() -> Fernet:
    return Fernet(get_settings().fernet_key.encode())


def encrypt(value: str) -> str:
    """Encrypt a plaintext string into a Fernet token (str)."""
    return get_fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a Fernet token (str) back into plaintext."""
    return get_fernet().decrypt(token.encode()).decode()


class EncryptedString(TypeDecorator):
    """Stored encrypted at rest; transparently encrypted/decrypted in Python."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return encrypt(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return decrypt(value)
