"""Thin HTTP client for the GoCardless Bank Account Data API.

Handles authentication (secret_id/secret_key -> short-lived access + refresh tokens, cached
in memory and refreshed automatically) and the endpoints Phase 1 needs. The client is
deliberately I/O-only: parsing into domain objects lives in the BankConnector.

Docs: https://developer.gocardless.com/bank-account-data/  (base URL
https://bankaccountdata.gocardless.com, all paths under /api/v2/).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import httpx

# Refresh a little before actual expiry to avoid races near the boundary.
_EXPIRY_SAFETY_SECONDS = 60


class GoCardlessError(RuntimeError):
    def __init__(self, status_code: int, detail: Any) -> None:
        super().__init__(f"GoCardless API error {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GoCardlessClient:
    def __init__(
        self,
        secret_id: str,
        secret_key: str,
        base_url: str = "https://bankaccountdata.gocardless.com",
        *,
        http_client: httpx.Client | None = None,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._secret_id = secret_id
        self._secret_key = secret_key
        self._clock = clock
        self._client = http_client or httpx.Client(base_url=base_url, timeout=30.0)

        self._access_token: str | None = None
        self._access_expiry: datetime | None = None
        self._refresh_token: str | None = None
        self._refresh_expiry: datetime | None = None

    # --- auth -------------------------------------------------------------

    def _valid(self, expiry: datetime | None) -> bool:
        return expiry is not None and self._clock() < expiry

    def _store_tokens(self, data: dict) -> None:
        now = self._clock()
        if "access" in data:
            self._access_token = data["access"]
            self._access_expiry = now + timedelta(
                seconds=int(data.get("access_expires", 86400)) - _EXPIRY_SAFETY_SECONDS
            )
        if "refresh" in data:
            self._refresh_token = data["refresh"]
            self._refresh_expiry = now + timedelta(
                seconds=int(data.get("refresh_expires", 2592000))
                - _EXPIRY_SAFETY_SECONDS
            )

    def _ensure_access_token(self) -> str:
        if self._valid(self._access_expiry) and self._access_token:
            return self._access_token
        if self._valid(self._refresh_expiry) and self._refresh_token:
            data = self._post("/api/v2/token/refresh/", {"refresh": self._refresh_token})
            self._store_tokens(data)
        else:
            data = self._post(
                "/api/v2/token/new/",
                {"secret_id": self._secret_id, "secret_key": self._secret_key},
            )
            self._store_tokens(data)
        assert self._access_token is not None
        return self._access_token

    # --- low-level requests ----------------------------------------------

    def _post(self, path: str, json: dict) -> dict:
        # Token endpoints are unauthenticated; everything else uses _request.
        response = self._client.post(path, json=json)
        return self._handle(response)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
    ) -> Any:
        token = self._ensure_access_token()
        response = self._client.request(
            method,
            path,
            params=params,
            json=json,
            headers={"Authorization": f"Bearer {token}"},
        )
        return self._handle(response)

    @staticmethod
    def _handle(response: httpx.Response) -> Any:
        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:  # noqa: BLE001
                detail = response.text
            raise GoCardlessError(response.status_code, detail)
        if not response.content:
            return None
        return response.json()

    # --- endpoints --------------------------------------------------------

    def get_institutions(self, country: str) -> list[dict]:
        return self._request("GET", "/api/v2/institutions/", params={"country": country})

    def create_requisition(
        self,
        *,
        institution_id: str,
        redirect: str,
        reference: str | None = None,
        agreement: str | None = None,
    ) -> dict:
        body: dict = {"institution_id": institution_id, "redirect": redirect}
        if reference is not None:
            body["reference"] = reference
        if agreement is not None:
            body["agreement"] = agreement
        return self._request("POST", "/api/v2/requisitions/", json=body)

    def get_requisition(self, requisition_id: str) -> dict:
        return self._request("GET", f"/api/v2/requisitions/{requisition_id}/")

    def delete_requisition(self, requisition_id: str) -> None:
        self._request("DELETE", f"/api/v2/requisitions/{requisition_id}/")

    def get_account_details(self, account_id: str) -> dict:
        return self._request("GET", f"/api/v2/accounts/{account_id}/details/")

    def get_account_balances(self, account_id: str) -> dict:
        return self._request("GET", f"/api/v2/accounts/{account_id}/balances/")

    def get_account_transactions(
        self, account_id: str, *, date_from: str | None = None
    ) -> dict:
        params = {"date_from": date_from} if date_from else None
        return self._request(
            "GET", f"/api/v2/accounts/{account_id}/transactions/", params=params
        )

    def close(self) -> None:
        self._client.close()
