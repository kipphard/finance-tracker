"""Application configuration via pydantic-settings.

All secrets and connection strings come from the environment / a local .env file —
never hard-coded and never committed (see §8 of the plan).
"""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Finance Tracker"
    debug: bool = False

    # SQLAlchemy URL, e.g. postgresql+psycopg://app:app@db:5432/finance
    database_url: str = "postgresql+psycopg://app:app@db:5432/finance"

    # Fernet key used to encrypt access tokens at rest. Required — no default,
    # so the app fails fast at startup if it is missing.
    fernet_key: str

    # Currency the net-worth headline total is summed in. No FX conversion in Phase 0.
    app_base_currency: str = "EUR"

    @field_validator("fernet_key")
    @classmethod
    def _validate_fernet_key(cls, value: str) -> str:
        try:
            Fernet(value.encode() if isinstance(value, str) else value)
        except Exception as exc:  # noqa: BLE001 - surface a clear config error
            raise ValueError(
                "FERNET_KEY is not a valid Fernet key. Generate one with: "
                'python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            ) from exc
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
