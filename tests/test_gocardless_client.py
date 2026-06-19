import pytest

from backend.connectors.gocardless.client import GoCardlessError
from gocardless_fixtures import build_mock_client


def test_token_fetched_once_and_reused():
    calls = []
    client = build_mock_client(token_calls=calls)
    first = client.get_institutions("DE")
    second = client.get_institutions("DE")
    assert calls == [1]  # /token/new/ hit exactly once, then cached
    assert first[0]["id"] == "BANK_DE"
    assert second[0]["id"] == "BANK_DE"


def test_api_error_raises():
    client = build_mock_client(fail_path="/api/v2/institutions/")
    with pytest.raises(GoCardlessError) as exc:
        client.get_institutions("DE")
    assert exc.value.status_code == 400
