"""A mock-transport GoCardless client for tests (no network, no real keys).

Simulates the token, institutions, requisition, account-details, balances, and transactions
endpoints with canned responses for one institution (BANK_DE) and two accounts
(acc-1: 1000.00 EUR + one transaction; acc-2: 250.50 EUR, no transactions).
"""
from __future__ import annotations

import json

import httpx

from backend.connectors.gocardless.client import GoCardlessClient

_INSTITUTIONS = [
    {
        "id": "BANK_DE",
        "name": "Test Bank",
        "bic": "TESTDEFF",
        "transaction_total_days": "90",
        "countries": ["DE"],
        "logo": "",
    }
]

_DETAILS = {
    "acc-1": {"resourceId": "acc-1", "iban": "DE89...", "currency": "EUR", "name": "Girokonto", "ownerName": "Andre", "product": "Current"},
    "acc-2": {"resourceId": "acc-2", "currency": "EUR", "name": "Tagesgeld"},
}

_BALANCES = {
    "acc-1": [{"balanceAmount": {"amount": "1000.00", "currency": "EUR"}, "balanceType": "closingBooked", "referenceDate": "2026-06-18"}],
    "acc-2": [{"balanceAmount": {"amount": "250.50", "currency": "EUR"}, "balanceType": "closingBooked", "referenceDate": "2026-06-18"}],
}

_TRANSACTIONS = {
    "acc-1": {"booked": [{"transactionId": "tx-1", "bookingDate": "2026-06-01", "transactionAmount": {"amount": "-12.34", "currency": "EUR"}, "remittanceInformationUnstructured": "Coffee", "creditorName": "Cafe"}], "pending": []},
    "acc-2": {"booked": [], "pending": []},
}


def _make_handler(token_calls: list | None, fail_path: str | None):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method
        if fail_path and path == fail_path:
            return httpx.Response(400, json={"detail": "boom"})

        if path == "/api/v2/token/new/":
            if token_calls is not None:
                token_calls.append(1)
            return httpx.Response(200, json={"access": "access-token", "access_expires": 86400, "refresh": "refresh-token", "refresh_expires": 2592000})
        if path == "/api/v2/token/refresh/":
            return httpx.Response(200, json={"access": "access-token-2", "access_expires": 86400})
        if path == "/api/v2/institutions/":
            return httpx.Response(200, json=_INSTITUTIONS)
        if path == "/api/v2/requisitions/" and method == "POST":
            body = json.loads(request.content or b"{}")
            return httpx.Response(201, json={"id": "req-1", "link": "https://bankaccountdata.gocardless.com/link/req-1", "status": "CR", "accounts": [], "reference": body.get("reference"), "institution_id": body.get("institution_id")})
        if path == "/api/v2/requisitions/req-1/" and method == "GET":
            return httpx.Response(200, json={"id": "req-1", "status": "LN", "accounts": ["acc-1", "acc-2"], "institution_id": "BANK_DE"})

        parts = path.strip("/").split("/")
        if len(parts) == 5 and parts[2] == "accounts":
            account_id, resource = parts[3], parts[4]
            if resource == "details":
                return httpx.Response(200, json={"account": _DETAILS.get(account_id, {})})
            if resource == "balances":
                return httpx.Response(200, json={"balances": _BALANCES.get(account_id, [])})
            if resource == "transactions":
                return httpx.Response(200, json={"transactions": _TRANSACTIONS.get(account_id, {"booked": [], "pending": []})})

        return httpx.Response(404, json={"detail": f"no mock for {method} {path}"})

    return handler


def build_mock_client(
    *, token_calls: list | None = None, fail_path: str | None = None
) -> GoCardlessClient:
    transport = httpx.MockTransport(_make_handler(token_calls, fail_path))
    http_client = httpx.Client(base_url="https://test.local", transport=transport)
    return GoCardlessClient("secret-id", "secret-key", "https://test.local", http_client=http_client)
