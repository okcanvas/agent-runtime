from __future__ import annotations

import asyncio
import json

import httpx

from groupware_mcp_server.app import create_app
from groupware_mcp_server.config import Settings
from groupware_mcp_server.groupware_client import HttpGroupwareClient
from groupware_mcp_server.identity import DelegatedIdentity


def test_downstream_permission_error_is_structured_and_secret_free() -> None:
    async def scenario() -> None:
        async def downstream(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={"message": "secret backend detail"})

        settings = Settings("connector-secret", "https://groupware.test", "groupware-secret")
        downstream_client = httpx.AsyncClient(transport=httpx.MockTransport(downstream))
        try:
            app = create_app(settings, groupware_client=HttpGroupwareClient(settings, downstream_client))
            identity = DelegatedIdentity.create(
                tenant_id="tenant-a", principal_id="user-001", roles=("agent-user",)
            )
            headers = {
                "Authorization": "Bearer connector-secret",
                "X-OKCanvas-Tenant-ID": "tenant-a",
                "X-OKCanvas-Principal-ID": "user-001",
                "X-OKCanvas-Roles": "agent-user",
                "X-OKCanvas-Delegation-ID": identity.delegation_id,
            }
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://connector"
            ) as client:
                response = await client.post(
                    "/tenants/tenant-a/mcp",
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": "x",
                        "method": "tools/call",
                        "params": {"name": "search_mail", "arguments": {}},
                    },
                )
            result = response.json()["result"]
            assert result["isError"] is True
            payload = json.loads(result["content"][0]["text"])
            assert payload["error_code"] == "GROUPWARE_PERMISSION_DENIED"
            assert payload["retryable"] is False
            assert "groupware-secret" not in json.dumps(response.json())
            assert "secret backend detail" not in json.dumps(response.json())
        finally:
            await downstream_client.aclose()

    asyncio.run(scenario())
