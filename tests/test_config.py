import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from backend.config import Settings


def test_valid_fernet_key_loads():
    settings = Settings(
        fernet_key=Fernet.generate_key().decode(), database_url="sqlite://"
    )
    assert settings.app_base_currency == "EUR"


def test_bad_fernet_key_fails_fast():
    with pytest.raises(ValidationError):
        Settings(fernet_key="not-a-valid-key", database_url="sqlite://")
