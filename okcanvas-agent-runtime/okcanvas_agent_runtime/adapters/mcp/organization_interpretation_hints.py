from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from okcanvas_agent_runtime.adapters.mcp.clients import create_openai_mcp_runtime
from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerCatalog
from okcanvas_agent_runtime.application.assistant_interpretation import (
    GroundedCapabilityHint,
    GroundedHintState,
    GroundedInterpretationContext,
    GroundedOrganizationBindingHint,
    GroundedOrganizationEntityHint,
    GroundedOrganizationHints,
    GroundedOrganizationTermHint,
    project_session_focus,
)
from okcanvas_agent_runtime.application.groupware_read import GroupwareReadCatalog, GroupwareReadState
from okcanvas_agent_runtime.application.mcp_access import (
    DelegatedMCPIdentity,
    MCPAccessCatalog,
    MCPPassiveHealthRegistry,
)
from okcanvas_agent_runtime.application.organization_context import (
    OrganizationContextReadCatalog,
    OrganizationContextReadState,
)
from okcanvas_agent_runtime.domain.sessions.context_focus import SessionContextFocusRecord

_HINT_SERVER_ID = "organization-context-interpretation-hints"
_ENTITY_TOOL = "search_organization_context"
_TERM_TOOL = "search_organization_terms"
_MAX_QUERY_CHARS = 500
_ENTITY_LIMIT = 8
_TERM_LIMIT = 5
_MAX_MODEL_MATCHED_BY = 8
_MAX_MODEL_POSITIONS = 8
_MAX_MODEL_BINDINGS = 8


class GroundedInterpretationHintContractError(RuntimeError):
    code = "GROUNDED_INTERPRETATION_HINT_CONTRACT_INVALID"


def _text(value: object, *, max_length: int) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.strip().split())
    if not normalized:
        return None
    return normalized[:max_length]


def _text_tuple(value: object, *, max_items: int, max_length: int) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    result: list[str] = []
    for item in value:
        text = _text(item, max_length=max_length)
        if text and text not in result:
            result.append(text)
        if len(result) >= max_items:
            break
    return tuple(result)


def _result_payload(result: Any) -> dict[str, Any]:
    if bool(getattr(result, "is_error", False) or getattr(result, "isError", False)):
        raise GroundedInterpretationHintContractError("Organization hint Tool returned an error result")
    for attribute in ("structured_content", "structuredContent"):
        value = getattr(result, attribute, None)
        if isinstance(value, dict):
            return value
    content = getattr(result, "content", None)
    if isinstance(content, list):
        for item in content:
            text = getattr(item, "text", None)
            if text is None and isinstance(item, dict):
                text = item.get("text")
            if isinstance(text, str):
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    return payload
    model_dump = getattr(result, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            structured = payload.get("structuredContent") or payload.get("structured_content")
            if isinstance(structured, dict):
                return structured
    raise GroundedInterpretationHintContractError("Organization hint Tool result has no structured payload")


def _validate_tool_result(
    payload: dict[str, Any], *, tool_name: str, identity: DelegatedMCPIdentity
) -> tuple[list[dict[str, Any]], int | None, bool]:
    if payload.get("tool_name") != tool_name:
        raise GroundedInterpretationHintContractError("Organization hint Tool identity drifted")
    if payload.get("mutated") is not False:
        raise GroundedInterpretationHintContractError("Organization hint Tool must be read-only")
    if payload.get("tenant_id") != identity.tenant_id or payload.get("principal_id") != identity.principal_id:
        raise GroundedInterpretationHintContractError("Organization hint delegated identity drifted")
    if payload.get("delegation_id") != identity.delegation_id:
        raise GroundedInterpretationHintContractError("Organization hint delegation fingerprint drifted")
    raw_roles = payload.get("roles")
    if not isinstance(raw_roles, list) or tuple(sorted(set(raw_roles))) != identity.roles:
        raise GroundedInterpretationHintContractError("Organization hint delegated roles drifted")
    records = payload.get("records")
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise GroundedInterpretationHintContractError("Organization hint records are invalid")
    revision = payload.get("catalog_revision")
    if revision is not None and (not isinstance(revision, int) or isinstance(revision, bool) or revision < 0):
        raise GroundedInterpretationHintContractError("Organization hint catalog revision is invalid")
    truncated = payload.get("truncated") is True
    return [dict(item) for item in records], revision, truncated


def _project_entity(record: dict[str, Any]) -> GroundedOrganizationEntityHint | None:
    entity_type = _text(record.get("entity_type"), max_length=64)
    display_name = _text(record.get("display_name"), max_length=300)
    if not entity_type or not display_name:
        return None
    context = record.get("context") if isinstance(record.get("context"), dict) else {}
    return GroundedOrganizationEntityHint(
        entity_type=entity_type,
        display_name=display_name,
        matched_by=_text_tuple(
            record.get("matched_by"), max_items=_MAX_MODEL_MATCHED_BY, max_length=80
        ),
        status=_text(record.get("status"), max_length=64),
        department_name=_text(context.get("department_name"), max_length=300),
        positions=_text_tuple(
            context.get("positions"), max_items=_MAX_MODEL_POSITIONS, max_length=200
        ),
    )


def _project_term(record: dict[str, Any]) -> GroundedOrganizationTermHint | None:
    canonical_name = _text(record.get("canonical_name"), max_length=300)
    if not canonical_name:
        return None
    bindings: list[GroundedOrganizationBindingHint] = []
    raw_bindings = record.get("bindings")
    if isinstance(raw_bindings, list):
        for item in raw_bindings:
            if not isinstance(item, dict):
                continue
            capability_id = _text(item.get("capability_id"), max_length=128)
            default_operation = _text(item.get("default_operation"), max_length=64)
            entity_type = _text(item.get("entity_type"), max_length=128)
            if not capability_id or not default_operation or not entity_type:
                continue
            bindings.append(
                GroundedOrganizationBindingHint(
                    capability_id=capability_id,
                    default_operation=default_operation,
                    entity_type=entity_type,
                    risk_level=_text(item.get("risk_level"), max_length=64),
                    system_id=_text(item.get("system_id"), max_length=128),
                )
            )
            if len(bindings) >= _MAX_MODEL_BINDINGS:
                break
    return GroundedOrganizationTermHint(
        canonical_name=canonical_name,
        definition=_text(record.get("definition"), max_length=800),
        classification=_text(record.get("classification"), max_length=128),
        bindings=tuple(bindings),
    )


class OrganizationGroundedInterpretationContextProvider:
    """Build turn-local, non-authoritative model hints from the production Organization SOT.

    The raw utterance is passed unchanged to the bounded search Tools. This provider never selects
    an Agent, intent, relation, stable entity identity, or final Tool. It only retrieves and projects
    facts that can help the LLM interpret the utterance. Final execution remains governed elsewhere.
    """

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self._mcp_catalog = MCPServerCatalog(self.project_root)
        self._access = MCPAccessCatalog(self.project_root)
        self._hint_server = self._mcp_catalog.resolve(_HINT_SERVER_ID)
        self._organization = OrganizationContextReadCatalog(self.project_root)
        self._groupware = GroupwareReadCatalog(self.project_root)
        self._validate_hint_profile()

    def _validate_hint_profile(self) -> None:
        execution = self._organization.server
        hint = self._hint_server
        if hint.schema_version != "okcanvas-mcp-server-v3" or not hint.read_only:
            raise GroundedInterpretationHintContractError("Organization hint MCP must be delegated read-only V3")
        if hint.allowed_tools != (_ENTITY_TOOL, _TERM_TOOL):
            raise GroundedInterpretationHintContractError("Organization hint MCP Tool allowlist drifted")
        if (
            hint.url_template != execution.url_template
            or hint.credential_ref != execution.credential_ref
            or hint.required_roles != execution.required_roles
            or hint.authorization_mode != execution.authorization_mode
            or hint.endpoint_mode != execution.endpoint_mode
        ):
            raise GroundedInterpretationHintContractError(
                "Organization hint MCP must share the execution Connector authority boundary"
            )
        if hint.max_result_chars > execution.max_result_chars:
            raise GroundedInterpretationHintContractError("Organization hint result bound exceeds execution MCP")

    def _capabilities(
        self, identity: DelegatedMCPIdentity | None
    ) -> tuple[GroundedCapabilityHint, ...]:
        org_ready = self._organization.readiness(identity).state is OrganizationContextReadState.READY
        groupware_ready = self._groupware.readiness(identity).state is GroupwareReadState.READY
        return (
            GroundedCapabilityHint(
                capability_id=self._organization.policy.capability_id,
                side_effect="READ",
                available=org_ready,
                operations=tuple(item.operation_id.upper() for item in self._organization.policy.operations),
            ),
            GroundedCapabilityHint(
                capability_id=self._groupware.policy.capability_id,
                side_effect="READ",
                available=groupware_ready,
                resources=("NOTICE", "MAIL", "CALENDAR"),
            ),
        )

    def _hint_endpoint_usable(self, identity: DelegatedMCPIdentity | None) -> bool:
        if identity is None:
            return False
        parsed = urlsplit(self._hint_server.url_template or "")
        if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.endswith(".invalid"):
            return False
        if not set(self._hint_server.required_roles).intersection(identity.roles):
            return False
        secret = self._access.secret_references.get(self._hint_server.credential_ref or "")
        if secret is None:
            return False
        return bool(os.environ.get(secret.environment_variable, "").strip())

    async def build(
        self,
        *,
        utterance: str,
        delegated_identity: DelegatedMCPIdentity | None,
        session_focus: SessionContextFocusRecord | None,
    ) -> GroundedInterpretationContext:
        capabilities = self._capabilities(delegated_identity)
        focus_hint = project_session_focus(session_focus)
        if len(utterance) > _MAX_QUERY_CHARS:
            hints = GroundedOrganizationHints(
                state=GroundedHintState.SKIPPED_INPUT_TOO_LONG,
                entity_state=GroundedHintState.SKIPPED_INPUT_TOO_LONG,
                term_state=GroundedHintState.SKIPPED_INPUT_TOO_LONG,
                catalog_revision=None,
                diagnostic_code="INPUT_TOO_LONG",
            )
            return GroundedInterpretationContext(focus_hint, capabilities, hints)
        if not utterance:
            hints = GroundedOrganizationHints(
                state=GroundedHintState.UNAVAILABLE,
                entity_state=GroundedHintState.UNAVAILABLE,
                term_state=GroundedHintState.UNAVAILABLE,
                catalog_revision=None,
                diagnostic_code="EMPTY_UTTERANCE",
            )
            return GroundedInterpretationContext(focus_hint, capabilities, hints)
        if delegated_identity is None:
            hints = GroundedOrganizationHints(
                state=GroundedHintState.UNAVAILABLE,
                entity_state=GroundedHintState.UNAVAILABLE,
                term_state=GroundedHintState.UNAVAILABLE,
                catalog_revision=None,
                diagnostic_code="DELEGATED_IDENTITY_UNAVAILABLE",
            )
            return GroundedInterpretationContext(focus_hint, capabilities, hints)
        if not self._hint_endpoint_usable(delegated_identity):
            hints = GroundedOrganizationHints(
                state=GroundedHintState.UNAVAILABLE,
                entity_state=GroundedHintState.UNAVAILABLE,
                term_state=GroundedHintState.UNAVAILABLE,
                catalog_revision=None,
                diagnostic_code="ENDPOINT_ROLE_OR_CREDENTIAL_UNAVAILABLE",
            )
            return GroundedInterpretationContext(focus_hint, capabilities, hints)

        try:
            access = self._access.bind_many((self._hint_server,), delegated_identity)
            runtime = create_openai_mcp_runtime(
                (self._hint_server,),
                project_root=self.project_root,
                access_bindings=access,
                health_registry=MCPPassiveHealthRegistry(),
            )
            async with runtime.manager as manager:
                if len(manager.active_servers) != 1:
                    raise GroundedInterpretationHintContractError(
                        "Organization hint MCP did not connect exactly one server"
                    )
                server = manager.active_servers[0]
                entity_result: Any | None = None
                term_result: Any | None = None
                entity_error = False
                term_error = False
                try:
                    entity_result = await server.call_tool(
                        _ENTITY_TOOL,
                        {"query": utterance, "entity_types": [], "organization_unit_id": None, "limit": _ENTITY_LIMIT},
                    )
                except Exception:
                    entity_error = True
                try:
                    term_result = await server.call_tool(
                        _TERM_TOOL,
                        {"query": utterance, "organization_unit_id": None, "limit": _TERM_LIMIT},
                    )
                except Exception:
                    term_error = True
        except Exception:
            hints = GroundedOrganizationHints(
                state=GroundedHintState.UNAVAILABLE,
                entity_state=GroundedHintState.UNAVAILABLE,
                term_state=GroundedHintState.UNAVAILABLE,
                catalog_revision=None,
                diagnostic_code="MCP_CONNECTION_UNAVAILABLE",
            )
            return GroundedInterpretationContext(focus_hint, capabilities, hints)

        entity_records: list[dict[str, Any]] = []
        term_records: list[dict[str, Any]] = []
        entity_revision: int | None = None
        term_revision: int | None = None
        entity_truncated = False
        term_truncated = False
        entity_state = GroundedHintState.UNAVAILABLE
        term_state = GroundedHintState.UNAVAILABLE

        if not entity_error and entity_result is not None:
            try:
                entity_records, entity_revision, entity_truncated = _validate_tool_result(
                    _result_payload(entity_result), tool_name=_ENTITY_TOOL, identity=delegated_identity
                )
                entity_state = GroundedHintState.AVAILABLE if entity_records else GroundedHintState.NO_MATCH
            except Exception:
                entity_state = GroundedHintState.UNAVAILABLE
        if not term_error and term_result is not None:
            try:
                term_records, term_revision, term_truncated = _validate_tool_result(
                    _result_payload(term_result), tool_name=_TERM_TOOL, identity=delegated_identity
                )
                term_state = GroundedHintState.AVAILABLE if term_records else GroundedHintState.NO_MATCH
            except Exception:
                term_state = GroundedHintState.UNAVAILABLE

        entities = tuple(item for record in entity_records if (item := _project_entity(record)) is not None)
        terms = tuple(item for record in term_records if (item := _project_term(record)) is not None)
        successful_states = {GroundedHintState.AVAILABLE, GroundedHintState.NO_MATCH}
        if entity_state in successful_states and term_state in successful_states:
            state = GroundedHintState.AVAILABLE if entities or terms else GroundedHintState.NO_MATCH
        elif entity_state in successful_states or term_state in successful_states:
            state = GroundedHintState.PARTIAL
        else:
            state = GroundedHintState.UNAVAILABLE
        revisions = [item for item in (entity_revision, term_revision) if item is not None]
        revision_consistent = len(set(revisions)) <= 1
        revision = revisions[0] if revisions and revision_consistent else None
        if state is GroundedHintState.AVAILABLE:
            diagnostic_code = "AVAILABLE"
        elif state is GroundedHintState.NO_MATCH:
            diagnostic_code = "NO_MATCH"
        elif state is GroundedHintState.PARTIAL:
            diagnostic_code = "PARTIAL_TOOL_OR_CONTRACT_UNAVAILABLE"
        else:
            diagnostic_code = "BOTH_TOOL_OR_CONTRACT_UNAVAILABLE"
        return GroundedInterpretationContext(
            session_focus=focus_hint,
            capabilities=capabilities,
            organization_hints=GroundedOrganizationHints(
                state=state,
                entity_state=entity_state,
                term_state=term_state,
                catalog_revision=revision,
                diagnostic_code=diagnostic_code,
                entity_catalog_revision=entity_revision,
                term_catalog_revision=term_revision,
                catalog_revision_consistent=revision_consistent,
                entities=entities,
                terms=terms,
                entity_result_count=len(entity_records),
                term_result_count=len(term_records),
                entity_truncated=entity_truncated,
                term_truncated=term_truncated,
            ),
        )
