from __future__ import annotations

import json
from typing import Any, Mapping

from .baseline import PROJECT_VERSION
from .identity import DelegatedIdentity, IdentityError
from .service import GroupwareReadService, ToolInvocationError

SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")

TOOLS: tuple[dict[str, Any], ...] = (
    {
        "name": "search_notices",
        "description": "Search notices visible to the delegated Groupware principal without mutation.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {"type": "string", "maxLength": 500, "default": ""},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
            },
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "search_mail",
        "description": "Search mailbox records visible to the delegated principal without changing read state.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {"type": "string", "maxLength": 500, "default": ""},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
            },
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "list_calendar_events",
        "description": "List calendar events visible to the delegated principal without mutation.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "start_at": {"type": ["string", "null"], "maxLength": 64, "default": None},
                "end_at": {"type": ["string", "null"], "maxLength": 64, "default": None},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
            },
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    },
)


class MCPProtocolHandler:
    def __init__(self, service: GroupwareReadService, *, connector_bearer: str) -> None:
        self._service = service
        self._connector_bearer = connector_bearer

    async def handle(
        self,
        payload: Any,
        *,
        headers: Mapping[str, str],
        path_tenant_id: str,
    ) -> tuple[int, dict[str, Any] | None]:
        if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
            return 400, _error(None, -32600, "Invalid JSON-RPC request")
        request_id = payload.get("id")
        method = payload.get("method")
        if not isinstance(method, str):
            return 400, _error(request_id, -32600, "JSON-RPC method is required")
        if request_id is None:
            if method == "notifications/initialized":
                return 202, None
            return 202, None
        try:
            identity = DelegatedIdentity.from_headers(
                {key.lower(): value for key, value in headers.items()},
                expected_bearer=self._connector_bearer,
            )
        except IdentityError as exc:
            return 401, _error(request_id, -32001, str(exc))
        if identity.tenant_id != path_tenant_id:
            return 403, _error(request_id, -32003, "Tenant path does not match delegated identity")
        if method == "initialize":
            params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
            requested = params.get("protocolVersion")
            protocol = requested if requested in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[0]
            return 200, _result(
                request_id,
                {
                    "protocolVersion": protocol,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {
                        "name": "okcanvas-groupware-mcp-server",
                        "version": PROJECT_VERSION,
                    },
                    "instructions": "Read-only Groupware connector. All Tools are non-mutating.",
                },
            )
        if method == "ping":
            return 200, _result(request_id, {})
        if method == "tools/list":
            return 200, _result(request_id, {"tools": list(TOOLS)})
        if method == "tools/call":
            params = payload.get("params")
            if not isinstance(params, dict) or not isinstance(params.get("name"), str):
                return 200, _error(request_id, -32602, "Tool call parameters are invalid")
            meta = params.get("_meta") if isinstance(params.get("_meta"), dict) else {}
            request_meta_id = meta.get("request_id") if isinstance(meta.get("request_id"), str) else None
            correlation_id = request_meta_id or f"mcp-{request_id}"
            try:
                result = await self._service.invoke(
                    params["name"],
                    params.get("arguments") if isinstance(params.get("arguments"), dict) else {},
                    identity=identity,
                    request_id=correlation_id,
                )
                structured = result.model_dump(mode="json")
                return 200, _result(
                    request_id,
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    structured,
                                    ensure_ascii=False,
                                    sort_keys=True,
                                    separators=(",", ":"),
                                ),
                            }
                        ],
                        "structuredContent": structured,
                        "isError": False,
                    },
                )
            except ToolInvocationError as exc:
                error_payload = exc.payload.model_dump(mode="json")
                return 200, _result(
                    request_id,
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    error_payload,
                                    ensure_ascii=False,
                                    sort_keys=True,
                                    separators=(",", ":"),
                                ),
                            }
                        ],
                        "structuredContent": error_payload,
                        "isError": True,
                    },
                )
        return 200, _error(request_id, -32601, "Method not found")


def _result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
