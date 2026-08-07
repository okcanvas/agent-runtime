from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from .config import Settings
from .identity import DelegatedIdentity


@dataclass(frozen=True, slots=True)
class OrganizationContextClientError(RuntimeError):
    code: str
    message: str
    retryable: bool
    http_status: int | None = None

    def __str__(self) -> str:
        return self.message


class HttpOrganizationContextClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client

    def _headers(self, identity: DelegatedIdentity, request_id: str, organization_unit_id: str | None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._settings.organization_context_api_bearer}",
            "Content-Type": "application/json",
            "X-Tenant-ID": identity.tenant_id,
            "X-Principal-ID": identity.principal_id,
            "X-Principal-Roles": ",".join(identity.roles),
            "X-Delegation-ID": identity.delegation_id,
            "X-Request-ID": request_id,
        }
        if organization_unit_id:
            headers["X-Organization-Unit-ID"] = organization_unit_id
        return headers

    async def request(
        self,
        method: str,
        path: str,
        *,
        identity: DelegatedIdentity,
        request_id: str,
        organization_unit_id: str | None = None,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._settings.organization_context_base_url}{path}"
        headers = self._headers(identity, request_id, organization_unit_id)
        attempts = self._settings.max_retry_attempts + 1
        for attempt in range(attempts):
            try:
                if self._client is None:
                    async with httpx.AsyncClient(
                        timeout=self._settings.http_timeout_seconds,
                        follow_redirects=False,
                        trust_env=False,
                    ) as client:
                        response = await client.request(method, url, headers=headers, json=body, params=params)
                else:
                    response = await self._client.request(method, url, headers=headers, json=body, params=params)
                if response.status_code in {429, 503} and attempt + 1 < attempts:
                    await asyncio.sleep(0.05 * (attempt + 1))
                    continue
                if response.status_code >= 400:
                    raise _map_status(response.status_code)
                try:
                    payload = response.json()
                except Exception as exc:
                    raise OrganizationContextClientError(
                        "ORGANIZATION_CONTEXT_MALFORMED_RESPONSE",
                        "Organization Context API returned a malformed response",
                        False,
                        response.status_code,
                    ) from exc
                if not isinstance(payload, dict):
                    raise OrganizationContextClientError(
                        "ORGANIZATION_CONTEXT_MALFORMED_RESPONSE",
                        "Organization Context API returned a malformed response",
                        False,
                        response.status_code,
                    )
                return payload
            except httpx.TimeoutException as exc:
                if attempt + 1 < attempts:
                    continue
                raise OrganizationContextClientError(
                    "ORGANIZATION_CONTEXT_TIMEOUT", "Organization Context API request timed out", True
                ) from exc
            except httpx.TransportError as exc:
                if attempt + 1 < attempts:
                    continue
                raise OrganizationContextClientError(
                    "ORGANIZATION_CONTEXT_UNAVAILABLE", "Organization Context API is unavailable", True
                ) from exc
        raise AssertionError("unreachable")

    async def resolve_context(self, *, identity: DelegatedIdentity, query: str, entity_types: list[str], organization_unit_id: str | None, limit: int, request_id: str) -> dict[str, Any]:
        return await self.request(
            "POST", "/api/v1/context/resolve", identity=identity, request_id=request_id,
            organization_unit_id=organization_unit_id,
            body={"query": query, "entity_types": entity_types, "organization_unit_id": organization_unit_id, "limit": limit},
        )

    async def search_context(self, *, identity: DelegatedIdentity, query: str, entity_types: list[str], organization_unit_id: str | None, limit: int, request_id: str) -> dict[str, Any]:
        return await self.request(
            "POST", "/api/v1/context/search", identity=identity, request_id=request_id,
            organization_unit_id=organization_unit_id,
            body={"query": query, "entity_types": entity_types, "organization_unit_id": organization_unit_id, "limit": limit},
        )

    async def get_entity(self, *, identity: DelegatedIdentity, entity_type: str, entity_id: str, request_id: str) -> dict[str, Any]:
        return await self.request(
            "GET", f"/api/v1/context/entities/{quote(entity_type, safe='')}/{quote(entity_id, safe='')}",
            identity=identity, request_id=request_id,
        )

    async def resolve(self, *, identity: DelegatedIdentity, query: str, organization_unit_id: str | None, limit: int, request_id: str) -> dict[str, Any]:
        return await self.request(
            "POST", "/api/v1/glossary/resolve", identity=identity, request_id=request_id,
            organization_unit_id=organization_unit_id,
            body={"query": query, "organization_unit_id": organization_unit_id, "limit": limit},
        )

    async def search(self, *, identity: DelegatedIdentity, query: str, organization_unit_id: str | None, limit: int, request_id: str) -> dict[str, Any]:
        return await self.request(
            "POST", "/api/v1/glossary/search", identity=identity, request_id=request_id,
            organization_unit_id=organization_unit_id,
            body={"query": query, "organization_unit_id": organization_unit_id, "limit": limit},
        )

    async def get_term(self, *, identity: DelegatedIdentity, term_id: str, request_id: str) -> dict[str, Any]:
        return await self.request(
            "GET", f"/api/v1/glossary/terms/{quote(term_id, safe='')}", identity=identity, request_id=request_id
        )

    async def catalog_state(self, *, identity: DelegatedIdentity, request_id: str) -> dict[str, Any]:
        return await self.request("GET", "/api/v1/glossary/catalog-state", identity=identity, request_id=request_id)

    async def changes(self, *, identity: DelegatedIdentity, after_revision: int, limit: int, request_id: str) -> dict[str, Any]:
        return await self.request(
            "GET", "/api/v1/glossary/changes", identity=identity, request_id=request_id,
            params={"after": after_revision, "limit": limit},
        )


def _map_status(status: int) -> OrganizationContextClientError:
    mapping = {
        400: ("ORGANIZATION_CONTEXT_INVALID_REQUEST", "Organization Context request was invalid", False),
        401: ("ORGANIZATION_CONTEXT_AUTHENTICATION_FAILED", "Organization Context authentication failed", False),
        403: ("ORGANIZATION_CONTEXT_PERMISSION_DENIED", "Organization Context permission denied", False),
        404: ("ORGANIZATION_CONTEXT_ENTITY_NOT_FOUND", "Organization Context entity was not found", False),
        409: ("ORGANIZATION_CONTEXT_VERSION_CONFLICT", "Organization Context version conflict", False),
        429: ("ORGANIZATION_CONTEXT_RATE_LIMITED", "Organization Context rate limit exceeded", True),
        500: ("ORGANIZATION_CONTEXT_INTERNAL_ERROR", "Organization Context internal error", True),
        503: ("ORGANIZATION_CONTEXT_UNAVAILABLE", "Organization Context service unavailable", True),
    }
    code, message, retryable = mapping.get(
        status, ("ORGANIZATION_CONTEXT_HTTP_ERROR", "Organization Context API request failed", status >= 500)
    )
    return OrganizationContextClientError(code, message, retryable, status)
