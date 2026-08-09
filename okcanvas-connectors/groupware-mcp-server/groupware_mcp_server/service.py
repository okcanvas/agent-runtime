from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from .contracts import CalendarInput, SearchInput, ToolError, ToolResult
from .groupware_client import GroupwareClientError, HttpGroupwareClient
from .identity import DelegatedIdentity

_RESULT_SCHEMAS = {
    "search_notices": "okcanvas-groupware-search-notices-result-v2",
    "search_mail": "okcanvas-groupware-search-mail-result-v2",
    "list_calendar_events": "okcanvas-groupware-list-calendar-events-result-v2",
}


class ToolInvocationError(RuntimeError):
    def __init__(self, payload: ToolError) -> None:
        super().__init__(payload.message)
        self.payload = payload


class GroupwareReadService:
    def __init__(self, client: HttpGroupwareClient) -> None:
        self._client = client

    async def invoke(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None,
        *,
        identity: DelegatedIdentity,
        request_id: str,
    ) -> ToolResult:
        context_ref = None
        parsed_limit = 20
        try:
            if tool_name == "search_notices":
                parsed = SearchInput.model_validate(arguments or {})
                context_ref = parsed.context_ref
                parsed_limit = parsed.limit
                records = await self._client.search_notices(
                    identity=identity,
                    query=parsed.query,
                    limit=parsed.limit,
                    context_ref=parsed.context_ref.model_dump(mode="json") if parsed.context_ref is not None else None,
                    request_id=request_id,
                )
            elif tool_name == "search_mail":
                parsed = SearchInput.model_validate(arguments or {})
                context_ref = parsed.context_ref
                parsed_limit = parsed.limit
                records = await self._client.search_mail(
                    identity=identity,
                    query=parsed.query,
                    limit=parsed.limit,
                    context_ref=parsed.context_ref.model_dump(mode="json") if parsed.context_ref is not None else None,
                    request_id=request_id,
                )
            elif tool_name == "list_calendar_events":
                parsed = CalendarInput.model_validate(arguments or {})
                context_ref = parsed.context_ref
                parsed_limit = parsed.limit
                records = await self._client.list_calendar_events(
                    identity=identity,
                    start_at=parsed.start_at,
                    end_at=parsed.end_at,
                    limit=parsed.limit,
                    context_ref=parsed.context_ref.model_dump(mode="json") if parsed.context_ref is not None else None,
                    request_id=request_id,
                )
            else:
                raise ToolInvocationError(
                    ToolError(
                        error_code="MCP_TOOL_NOT_ALLOWED",
                        message="The requested MCP Tool is not allowed",
                        retryable=False,
                        request_id=request_id,
                    )
                )
        except ValidationError as exc:
            raise ToolInvocationError(
                ToolError(
                    error_code="MCP_INVALID_ARGUMENTS",
                    message="MCP Tool arguments are invalid",
                    retryable=False,
                    request_id=request_id,
                )
            ) from exc
        except GroupwareClientError as exc:
            raise ToolInvocationError(
                ToolError(
                    error_code=exc.code,
                    message=exc.message,
                    retryable=exc.retryable,
                    http_status=exc.http_status,
                    request_id=request_id,
                )
            ) from exc
        return ToolResult(
            result_schema_version=_RESULT_SCHEMAS[tool_name],
            tool_name=tool_name,
            context_ref=context_ref,
            tenant_id=identity.tenant_id,
            principal_id=identity.principal_id,
            roles=list(identity.roles),
            delegation_id=identity.delegation_id,
            records=records[:parsed_limit],
            request_id=request_id,
        )
