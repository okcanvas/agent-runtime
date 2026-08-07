import asyncio

from organization_context_mcp_server.identity import DelegatedIdentity
from organization_context_mcp_server.mcp_protocol import MCPProtocolHandler
from organization_context_mcp_server.contracts import ToolResult


class StubService:
    async def invoke(self, tool_name, arguments, *, identity, request_id):
        return ToolResult(
            result_schema_version="schema-v1",
            tool_name=tool_name,
            tenant_id=identity.tenant_id,
            principal_id=identity.principal_id,
            roles=list(identity.roles),
            organization_unit_id=arguments.get("organization_unit_id"),
            delegation_id=identity.delegation_id,
            catalog_revision=500,
            resolved=True,
            ambiguous=False,
            records=[{"entity_type": "EMPLOYEE", "entity_id": "employee-0017"}],
            changes=[],
            request_id=request_id,
        )


def headers(identity: DelegatedIdentity) -> dict[str, str]:
    return {
        "authorization": "Bearer connector-secret",
        "x-okcanvas-tenant-id": identity.tenant_id,
        "x-okcanvas-principal-id": identity.principal_id,
        "x-okcanvas-roles": ",".join(identity.roles),
        "x-okcanvas-delegation-id": identity.delegation_id,
    }


def test_initialize_list_and_call() -> None:
    identity = DelegatedIdentity.create(
        tenant_id="tenant-a", principal_id="user-001", roles=("agent-user", "employee")
    )
    handler = MCPProtocolHandler(StubService(), connector_bearer="connector-secret")

    async def run():
        initialized = await handler.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            headers=headers(identity), path_tenant_id="tenant-a",
        )
        listed = await handler.handle(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=headers(identity), path_tenant_id="tenant-a",
        )
        called = await handler.handle(
            {
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "resolve_organization_context", "arguments": {"query": "플랫폼팀 김민수 선임", "entity_types": ["EMPLOYEE"], "organization_unit_id": "department.platform-development"}, "_meta": {"request_id": "run-001-tool-001"}},
            },
            headers=headers(identity), path_tenant_id="tenant-a",
        )
        return initialized, listed, called

    initialized, listed, called = asyncio.run(run())
    assert initialized[0] == 200
    assert len(listed[1]["result"]["tools"]) == 8
    structured = called[1]["result"]["structuredContent"]
    assert structured["tool_name"] == "resolve_organization_context"
    assert structured["records"][0]["entity_id"] == "employee-0017"
    assert structured["mutated"] is False
