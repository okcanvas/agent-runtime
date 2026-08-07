import asyncio
import json

import httpx

from organization_context_mcp_server.config import Settings
from organization_context_mcp_server.identity import DelegatedIdentity
from organization_context_mcp_server.organization_context_client import (
    HttpOrganizationContextClient,
    OrganizationContextClientError,
)


def identity() -> DelegatedIdentity:
    return DelegatedIdentity.create(
        tenant_id="tenant-a", principal_id="user-001", roles=("employee", "agent-user")
    )


def test_unified_client_forwards_context_and_entity_types() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["headers"] = dict(request.headers)
        captured["json"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={
            "catalog_revision": 500,
            "resolved": True,
            "ambiguous": False,
            "matches": [{"entity_type": "EMPLOYEE", "entity_id": "employee-0017"}],
        })

    async def run() -> dict[str, object]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://product") as http:
            client = HttpOrganizationContextClient(
                Settings("connector-secret", "http://product", "product-secret", 2, 0), http
            )
            return await client.resolve_context(
                identity=identity(), query="플랫폼팀 김민수 선임", entity_types=["EMPLOYEE"],
                organization_unit_id="department.platform-development", limit=20, request_id="request-001"
            )

    payload = asyncio.run(run())
    headers = captured["headers"]
    body = captured["json"]
    assert captured["path"] == "/api/v1/context/resolve"
    assert isinstance(headers, dict) and headers["x-tenant-id"] == "tenant-a"
    assert headers["x-organization-unit-id"] == "department.platform-development"
    assert isinstance(body, dict) and body["entity_types"] == ["EMPLOYEE"]
    assert payload["resolved"] is True


def test_get_entity_path_is_encoded_and_normalized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/context/entities/CLIENT/client-0042"
        return httpx.Response(200, json={"catalog_revision": 500, "record": {"entity_id": "client-0042"}})

    async def run() -> dict[str, object]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://product") as http:
            client = HttpOrganizationContextClient(Settings("connector-secret", "http://product", "product-secret", 2, 0), http)
            return await client.get_entity(identity=identity(), entity_type="CLIENT", entity_id="client-0042", request_id="request-002")

    assert asyncio.run(run())["record"]["entity_id"] == "client-0042"


def test_permission_error_is_normalized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "denied"})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://product") as http:
            client = HttpOrganizationContextClient(Settings("connector-secret", "http://product", "product-secret", 2, 0), http)
            try:
                await client.catalog_state(identity=identity(), request_id="request-003")
            except OrganizationContextClientError as exc:
                assert exc.code == "ORGANIZATION_CONTEXT_PERMISSION_DENIED"
                assert exc.retryable is False
                assert exc.http_status == 403
            else:
                raise AssertionError("permission mapping was not raised")

    asyncio.run(run())
