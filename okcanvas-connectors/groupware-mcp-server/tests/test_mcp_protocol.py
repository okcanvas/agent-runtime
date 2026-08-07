from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from groupware_mcp_server.app import create_app
from groupware_mcp_server.config import Settings
from groupware_mcp_server.groupware_client import HttpGroupwareClient
from groupware_mcp_server.identity import DelegatedIdentity


@pytest.fixture
def identity() -> DelegatedIdentity:
    return DelegatedIdentity.create(
        tenant_id="tenant-a", principal_id="user-001", roles=("agent-user", "employee")
    )


def _headers(identity: DelegatedIdentity) -> dict[str, str]:
    return {
        "Authorization": "Bearer connector-secret",
        "X-OKCanvas-Tenant-ID": identity.tenant_id,
        "X-OKCanvas-Principal-ID": identity.principal_id,
        "X-OKCanvas-Roles": ",".join(identity.roles),
        "X-OKCanvas-Delegation-ID": identity.delegation_id,
        "Accept": "application/json, text/event-stream",
    }


def test_initialize_list_and_call_are_real_streamable_http_json_rpc(
    identity: DelegatedIdentity,
) -> None:
    async def scenario() -> None:
        async def downstream(request: httpx.Request) -> httpx.Response:
            assert request.headers["x-tenant-id"] == "tenant-a"
            assert request.headers["x-principal-id"] == "user-001"
            assert request.headers["x-principal-roles"] == "agent-user,employee"
            assert request.headers["authorization"] == "Bearer groupware-secret"
            body = json.loads(request.content)
            assert body == {"limit": 3, "query": "maintenance"}
            return httpx.Response(
                200,
                json={"records": [{"record_id": "notice-001", "title": "Maintenance"}]},
            )

        settings = Settings(
            connector_bearer="connector-secret",
            groupware_base_url="https://groupware.example.test",
            groupware_api_bearer="groupware-secret",
        )
        downstream_client = httpx.AsyncClient(transport=httpx.MockTransport(downstream))
        try:
            app = create_app(settings, groupware_client=HttpGroupwareClient(settings, downstream_client))
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://connector"
            ) as client:
                initialize = await client.post(
                    "/tenants/tenant-a/mcp",
                    headers=_headers(identity),
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-06-18",
                            "capabilities": {},
                            "clientInfo": {"name": "test", "version": "1"},
                        },
                    },
                )
                assert initialize.status_code == 200
                assert initialize.json()["result"]["capabilities"]["tools"]["listChanged"] is False
                assert initialize.json()["result"]["serverInfo"]["version"] == "0.1.1"
                tools = await client.post(
                    "/tenants/tenant-a/mcp",
                    headers=_headers(identity),
                    json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                )
                assert [item["name"] for item in tools.json()["result"]["tools"]] == [
                    "search_notices",
                    "search_mail",
                    "list_calendar_events",
                ]
                called = await client.post(
                    "/tenants/tenant-a/mcp",
                    headers=_headers(identity),
                    json={
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": "search_notices",
                            "arguments": {"query": "maintenance", "limit": 3},
                        },
                    },
                )
                result = called.json()["result"]
                assert result["isError"] is False
                structured = result["structuredContent"]
                assert structured["mutated"] is False
                assert structured["records"][0]["record_id"] == "notice-001"
                assert structured["roles"] == ["agent-user", "employee"]
        finally:
            await downstream_client.aclose()

    asyncio.run(scenario())


def test_tenant_mismatch_fails_before_downstream(identity: DelegatedIdentity) -> None:
    async def scenario() -> None:
        settings = Settings(
            connector_bearer="connector-secret",
            groupware_base_url="https://groupware.example.test",
            groupware_api_bearer="groupware-secret",
        )
        app = create_app(settings)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://connector"
        ) as client:
            response = await client.post(
                "/tenants/tenant-b/mcp",
                headers=_headers(identity),
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            )
            assert response.status_code == 403
            assert response.json()["error"]["code"] == -32003

    asyncio.run(scenario())
