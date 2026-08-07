from __future__ import annotations

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from .baseline import CURRENT_STEP, PROJECT_VERSION
from .config import Settings
from .groupware_client import HttpGroupwareClient
from .mcp_protocol import MCPProtocolHandler
from .service import GroupwareReadService


def create_app(
    settings: Settings | None = None,
    *,
    groupware_client: HttpGroupwareClient | None = None,
) -> FastAPI:
    resolved = settings or Settings.from_env()
    client = groupware_client or HttpGroupwareClient(resolved)
    handler = MCPProtocolHandler(
        GroupwareReadService(client), connector_bearer=resolved.connector_bearer
    )
    app = FastAPI(title="OKCanvas Groupware MCP Server", version=PROJECT_VERSION)

    @app.get("/healthz")
    async def healthz() -> dict[str, object]:
        return {
            "state": "READY",
            "step": CURRENT_STEP,
            "version": PROJECT_VERSION,
            "read_only": True,
            "tool_count": 3,
        }

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
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Invalid JSON"},
                },
            )
        status, body = await handler.handle(
            payload,
            headers=dict(request.headers),
            path_tenant_id=tenant_id,
        )
        if body is None:
            return Response(status_code=status)
        return JSONResponse(status_code=status, content=body)

    return app
