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

    # GoCardless Bank Account Data (Phase 1). Optional: the bank endpoints return 503 until
    # both credentials are set. Get the pair from the portal's "User Secrets" section.
    gocardless_secret_id: str | None = None
    gocardless_secret_key: str | None = None
    gocardless_base_url: str = "https://bankaccountdata.gocardless.com"
    # Where the bank sends the user back after consent (SCA). Phase 1 has no frontend yet,
    # so this points at the backend callback; finalize the requisition from there.
    gocardless_redirect_url: str = "http://localhost:8000/banks/callback"
    gocardless_country: str = "DE"

    @property
    def gocardless_configured(self) -> bool:
        return bool(self.gocardless_secret_id and self.gocardless_secret_key)

    # Auth (Phase 6). JWT signing secret falls back to the Fernet key if unset, so no extra
    # server secret is required. Tokens are HS256 bearer tokens.
    jwt_secret: str | None = None
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    @property
    def effective_jwt_secret(self) -> str:
        return self.jwt_secret or self.fernet_key

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
