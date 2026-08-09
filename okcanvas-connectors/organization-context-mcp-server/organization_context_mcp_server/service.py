from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from .contracts import ChangeInput, ContextResolveInput, ContextSearchInput, EmptyInput, GetEntityInput, GetTermInput, ResolveInput, SearchInput, ToolError, ToolResult
from .identity import DelegatedIdentity
from .organization_context_client import HttpOrganizationContextClient, OrganizationContextClientError

_RESULT_SCHEMAS = {
    "resolve_organization_context": "okcanvas-organization-context-unified-resolve-tool-result-v1",
    "search_organization_context": "okcanvas-organization-context-unified-search-tool-result-v1",
    "get_organization_entity": "okcanvas-organization-context-get-entity-tool-result-v1",
    "resolve_organization_terms": "okcanvas-organization-context-resolve-tool-result-v1",
    "search_organization_terms": "okcanvas-organization-context-search-tool-result-v1",
    "get_organization_term": "okcanvas-organization-context-get-term-tool-result-v1",
    "get_organization_catalog_state": "okcanvas-organization-context-catalog-state-tool-result-v1",
    "get_organization_changes": "okcanvas-organization-context-change-feed-tool-result-v1",
}


class ToolInvocationError(RuntimeError):
    def __init__(self, payload: ToolError) -> None:
        super().__init__(payload.message)
        self.payload = payload


def _validate_get_entity_relation_completeness(record: object, *, request_id: str) -> None:
    if not isinstance(record, dict):
        raise ToolInvocationError(ToolError(
            error_code="ORGANIZATION_CONTEXT_RELATION_COMPLETENESS_INVALID",
            message="Organization Context entity response lacks relationship completeness evidence",
            retryable=False, request_id=request_id,
        ))
    relations = record.get("relations")
    relation_count = record.get("relation_count")
    returned_count = record.get("relations_returned_count")
    truncated = record.get("relations_truncated")
    valid = (
        isinstance(relations, list)
        and isinstance(relation_count, int) and not isinstance(relation_count, bool) and relation_count >= 0
        and isinstance(returned_count, int) and not isinstance(returned_count, bool) and returned_count >= 0
        and isinstance(truncated, bool)
        and returned_count == len(relations)
        and relation_count >= returned_count
        and ((relation_count > returned_count) == truncated)
    )
    if not valid:
        raise ToolInvocationError(ToolError(
            error_code="ORGANIZATION_CONTEXT_RELATION_COMPLETENESS_INVALID",
            message="Organization Context entity response has inconsistent relationship completeness evidence",
            retryable=False, request_id=request_id,
        ))


class OrganizationContextReadService:
    def __init__(self, client: HttpOrganizationContextClient) -> None:
        self._client = client

    async def invoke(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None,
        *,
        identity: DelegatedIdentity,
        request_id: str,
    ) -> ToolResult:
        organization_unit_id: str | None = None
        try:
            if tool_name == "resolve_organization_context":
                parsed = ContextResolveInput.model_validate(arguments or {})
                organization_unit_id = parsed.organization_unit_id
                payload = await self._client.resolve_context(
                    identity=identity, query=parsed.query, entity_types=list(parsed.entity_types),
                    organization_unit_id=parsed.organization_unit_id, limit=parsed.limit, request_id=request_id,
                )
                records = list(payload.get("matches", []))
                changes: list[dict[str, Any]] = []
                resolved = bool(payload.get("resolved"))
                ambiguous = bool(payload.get("ambiguous"))
            elif tool_name == "search_organization_context":
                parsed = ContextSearchInput.model_validate(arguments or {})
                organization_unit_id = parsed.organization_unit_id
                payload = await self._client.search_context(
                    identity=identity, query=parsed.query, entity_types=list(parsed.entity_types),
                    organization_unit_id=parsed.organization_unit_id, limit=parsed.limit, request_id=request_id,
                )
                records = list(payload.get("matches", []))
                changes = []
                resolved = None
                ambiguous = None
            elif tool_name == "get_organization_entity":
                parsed = GetEntityInput.model_validate(arguments or {})
                payload = await self._client.get_entity(
                    identity=identity, entity_type=parsed.entity_type, entity_id=parsed.entity_id, request_id=request_id,
                )
                record = payload.get("record")
                _validate_get_entity_relation_completeness(record, request_id=request_id)
                records = [record] if isinstance(record, dict) else []
                changes = []
                resolved = None
                ambiguous = None
            elif tool_name == "resolve_organization_terms":
                parsed = ResolveInput.model_validate(arguments or {})
                organization_unit_id = parsed.organization_unit_id
                payload = await self._client.resolve(
                    identity=identity, query=parsed.query,
                    organization_unit_id=parsed.organization_unit_id,
                    limit=parsed.limit, request_id=request_id,
                )
                records = list(payload.get("matches", []))
                changes: list[dict[str, Any]] = []
                resolved = bool(payload.get("resolved"))
                ambiguous = bool(payload.get("ambiguous"))
            elif tool_name == "search_organization_terms":
                parsed = SearchInput.model_validate(arguments or {})
                organization_unit_id = parsed.organization_unit_id
                payload = await self._client.search(
                    identity=identity, query=parsed.query,
                    organization_unit_id=parsed.organization_unit_id,
                    limit=parsed.limit, request_id=request_id,
                )
                records = list(payload.get("records", []))
                changes = []
                resolved = None
                ambiguous = None
            elif tool_name == "get_organization_term":
                parsed = GetTermInput.model_validate(arguments or {})
                payload = await self._client.get_term(identity=identity, term_id=parsed.term_id, request_id=request_id)
                record = payload.get("record")
                records = [record] if isinstance(record, dict) else []
                changes = []
                resolved = None
                ambiguous = None
            elif tool_name == "get_organization_catalog_state":
                EmptyInput.model_validate(arguments or {})
                payload = await self._client.catalog_state(identity=identity, request_id=request_id)
                records = [{"effective_at": payload.get("effective_at"), "production_sot": payload.get("production_sot"), "example_sot": payload.get("example_sot"), "dataset_counts": payload.get("dataset_counts"), "fixture_valid": payload.get("fixture_valid"), "fixture_role": payload.get("fixture_role")}]
                changes = []
                resolved = None
                ambiguous = None
            elif tool_name == "get_organization_changes":
                parsed = ChangeInput.model_validate(arguments or {})
                payload = await self._client.changes(
                    identity=identity, after_revision=parsed.after_revision,
                    limit=parsed.limit, request_id=request_id,
                )
                records = []
                changes = list(payload.get("changes", []))
                resolved = None
                ambiguous = None
            else:
                raise ToolInvocationError(ToolError(
                    error_code="MCP_TOOL_NOT_ALLOWED", message="The requested MCP Tool is not allowed",
                    retryable=False, request_id=request_id,
                ))
        except ValidationError as exc:
            raise ToolInvocationError(ToolError(
                error_code="MCP_INVALID_ARGUMENTS", message="MCP Tool arguments are invalid",
                retryable=False, request_id=request_id,
            )) from exc
        except OrganizationContextClientError as exc:
            raise ToolInvocationError(ToolError(
                error_code=exc.code, message=exc.message, retryable=exc.retryable,
                http_status=exc.http_status, request_id=request_id,
            )) from exc
        catalog_revision = payload.get("catalog_revision", payload.get("current_revision"))
        return ToolResult(
            result_schema_version=_RESULT_SCHEMAS[tool_name], tool_name=tool_name,
            tenant_id=identity.tenant_id, principal_id=identity.principal_id,
            roles=list(identity.roles), organization_unit_id=organization_unit_id,
            delegation_id=identity.delegation_id,
            catalog_revision=int(catalog_revision) if isinstance(catalog_revision, int) else None,
            resolved=resolved, ambiguous=ambiguous,
            records=[item for item in records if isinstance(item, dict)][:100],
            changes=[item for item in changes if isinstance(item, dict)][:200],
            response_shape=str(payload.get("response_shape")) if payload.get("response_shape") is not None else None,
            candidate_count=int(payload["candidate_count"]) if isinstance(payload.get("candidate_count"), int) else None,
            returned_count=int(payload["returned_count"]) if isinstance(payload.get("returned_count"), int) else None,
            truncated=bool(payload["truncated"]) if isinstance(payload.get("truncated"), bool) else None,
            request_id=request_id,
        )
