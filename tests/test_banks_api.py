from decimal import Decimal

import pytest

from backend.api.deps import get_gocardless_client
from backend.main import app
from gocardless_fixtures import build_mock_client


@pytest.fixture
def bank_client(client):
    app.dependency_overrides[get_gocardless_client] = lambda: build_mock_client()
    return client


def test_full_bank_flow_via_api(bank_client):
    institutions = bank_client.get("/banks/institutions").json()
    assert institutions[0]["id"] == "BANK_DE"

    created = bank_client.post("/banks/requisitions", json={"institution_id": "BANK_DE"})
    assert created.status_code == 201
    body = created.json()
    assert body["requisition_id"] == "req-1"
    assert body["link"]
    connection_id = body["connection_id"]

    finalized = bank_client.post("/banks/requisitions/req-1/finalize")
    assert finalized.status_code == 200
    assert len(finalized.json()["accounts"]) == 2

    synced = bank_client.post(f"/banks/connections/{connection_id}/sync").json()
    assert synced["new_transactions"] == 1
    assert synced["balances_recorded"] == 2

    net_worth = bank_client.get("/networth").json()
    assert Decimal(str(net_worth["total"])) == Decimal("1250.50")

    connections = bank_client.get("/banks/connections").json()
    assert len(connections) == 1
    assert connections[0]["status"] == "active"

    assert bank_client.delete(f"/banks/connections/{connection_id}").status_code == 204
    after = bank_client.get("/networth").json()
    assert Decimal(str(after["total"])) == Decimal("0")


def test_banks_endpoint_503_when_not_configured(client):
    # No client override: GoCardless is unconfigured in tests, so the dep returns 503.
    assert client.get("/banks/institutions").status_code == 503
