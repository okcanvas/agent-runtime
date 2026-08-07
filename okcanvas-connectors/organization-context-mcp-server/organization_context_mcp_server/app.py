from __future__ import annotations

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from .baseline import CURRENT_STEP, PROJECT_VERSION
from .config import Settings
from .mcp_protocol import MCPProtocolHandler
from .organization_context_client import HttpOrganizationContextClient
from .service import OrganizationContextReadService


def create_app(settings: Settings | None = None, *, organization_context_client: HttpOrganizationContextClient | None = None) -> FastAPI:
    resolved = settings or Settings.from_env()
    client = organization_context_client or HttpOrganizationContextClient(resolved)
    handler = MCPProtocolHandler(OrganizationContextReadService(client), connector_bearer=resolved.connector_bearer)
    app = FastAPI(title="OKCanvas Organization Context MCP Server", version=PROJECT_VERSION)

    @app.get("/healthz")
    async def healthz() -> dict[str, object]:
        return {"state": "READY", "step": CURRENT_STEP, "version": PROJECT_VERSION, "read_only": True, "tool_count": 8}

    @app.get("/tenants/{tenant_id}/mcp")
    async def mcp_get(tenant_id: str) -> Response:
        return Response(status_code=405, headers={"Allow": "POST"})

    @app.delete("/tenants/{tenant_id}/mcp")
    async def mcp_delete(tenant_id: str) -> Response:
        return Response(status_code=405, headers={"Allow": "POST"})

    @app.post("/tenants/{tenant_id}/mcp")
    async def mcp_post(tenant_id: str, request: Request) -> Response:
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Invalid JSON"}})
        status, body = await handler.handle(payload, headers=dict(request.headers), path_tenant_id=tenant_id)
        if body is None:
            return Response(status_code=status)
        return JSONResponse(status_code=status, content=body)

    return app
