from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings
from .contracts import GroupwareApiResponse
from .identity import DelegatedIdentity


@dataclass(frozen=True)
class GroupwareClientError(RuntimeError):
    code: str
    message: str
    retryable: bool
    http_status: int | None = None

    def __str__(self) -> str:
        return self.message


class HttpGroupwareClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client

    async def search_notices(
        self, *, identity: DelegatedIdentity, query: str, limit: int, request_id: str
    ) -> list[dict[str, Any]]:
        return await self._post(
            self._settings.notices_path,
            identity=identity,
            body={"query": query, "limit": limit},
            request_id=request_id,
        )

    async def search_mail(
        self, *, identity: DelegatedIdentity, query: str, limit: int, request_id: str
    ) -> list[dict[str, Any]]:
        return await self._post(
            self._settings.mail_path,
            identity=identity,
            body={"query": query, "limit": limit},
            request_id=request_id,
        )

    async def list_calendar_events(
        self,
        *,
        identity: DelegatedIdentity,
        start_at: str | None,
        end_at: str | None,
        limit: int,
        request_id: str,
    ) -> list[dict[str, Any]]:
        body: dict[str, Any] = {"limit": limit}
        if start_at is not None and end_at is not None:
            body.update({"start_at": start_at, "end_at": end_at})
        return await self._post(
            self._settings.calendar_path,
            identity=identity,
            body=body,
            request_id=request_id,
        )

    async def _post(
        self,
        path: str,
        *,
        identity: DelegatedIdentity,
        body: dict[str, Any],
        request_id: str,
    ) -> list[dict[str, Any]]:
        url = f"{self._settings.groupware_base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._settings.groupware_api_bearer}",
            "Content-Type": "application/json",
            "X-Tenant-ID": identity.tenant_id,
            "X-Principal-ID": identity.principal_id,
            "X-Principal-Roles": ",".join(identity.roles),
            "X-Delegation-ID": identity.delegation_id,
            "X-Request-ID": request_id,
        }
        attempts = self._settings.max_retry_attempts + 1
        for attempt in range(attempts):
            try:
                if self._client is None:
                    async with httpx.AsyncClient(
                        timeout=self._settings.http_timeout_seconds,
                        follow_redirects=False,
                        trust_env=False,
                    ) as client:
                        response = await client.post(url, headers=headers, json=body)
                else:
                    response = await self._client.post(url, headers=headers, json=body)
                if response.status_code in {429, 503} and attempt + 1 < attempts:
                    await asyncio.sleep(0.05 * (attempt + 1))
                    continue
                if response.status_code >= 400:
                    raise _map_status(response.status_code)
                try:
                    payload = response.json()
                    parsed = GroupwareApiResponse.model_validate(payload)
                except Exception as exc:
                    raise GroupwareClientError(
                        "GROUPWARE_MALFORMED_RESPONSE",
                        "Groupware API returned a malformed response",
                        False,
                        response.status_code,
                    ) from exc
                return parsed.records
            except httpx.TimeoutException as exc:
                if attempt + 1 < attempts:
                    continue
                raise GroupwareClientError(
                    "GROUPWARE_TIMEOUT", "Groupware API request timed out", True
                ) from exc
            except httpx.TransportError as exc:
                if attempt + 1 < attempts:
                    continue
                raise GroupwareClientError(
                    "GROUPWARE_UNAVAILABLE", "Groupware API is unavailable", True
                ) from exc
        raise AssertionError("unreachable")


def _map_status(status: int) -> GroupwareClientError:
    mapping = {
        401: ("GROUPWARE_AUTHENTICATION_FAILED", "Groupware authentication failed", False),
        403: ("GROUPWARE_PERMISSION_DENIED", "Groupware permission denied", False),
        404: ("GROUPWARE_RESOURCE_NOT_FOUND", "Groupware resource was not found", False),
        409: ("GROUPWARE_VERSION_CONFLICT", "Groupware version conflict", False),
        429: ("GROUPWARE_RATE_LIMITED", "Groupware rate limit exceeded", True),
        500: ("GROUPWARE_INTERNAL_ERROR", "Groupware internal error", True),
        503: ("GROUPWARE_UNAVAILABLE", "Groupware service unavailable", True),
    }
    code, message, retryable = mapping.get(
        status, ("GROUPWARE_HTTP_ERROR", "Groupware API request failed", status >= 500)
    )
    return GroupwareClientError(code, message, retryable, status)
