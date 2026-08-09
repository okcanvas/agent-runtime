from __future__ import annotations

import json
from typing import Literal, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from okcanvas_agent_runtime.application.assistant_routing.grounded_delegation import (
    grounded_structured_delegation_context,
    grounded_structured_delegation_requested,
)
from okcanvas_agent_runtime.application.assistant_routing.models import (
    GroupwareContextFilterHint,
    OrganizationContextPreferredOperation,
    OrganizationContextRequestHint,
)
from okcanvas_agent_runtime.application.groupware_read import GroupwareReadCatalog, GroupwareReadState
from okcanvas_agent_runtime.application.mcp_access import DelegatedMCPIdentity
from okcanvas_agent_runtime.application.organization_context import (
    OrganizationContextReadCatalog,
    OrganizationContextReadState,
)
from okcanvas_agent_runtime.domain.sessions.context_focus import (
    SessionContextFocusRecord,
    SessionContextFocusState,
)

_ROOT_AGENT_ID = "organization-assistant-session-agent"
_ALLOWED_ENTITY_TYPES = {
    "TERM", "DEPARTMENT", "POSITION", "EMPLOYEE", "PRODUCT", "CLIENT", "PROJECT",
    "SYSTEM", "CAPABILITY",
}
_GROUPWARE_CONTEXT_ENTITY_TYPES = {"EMPLOYEE", "PROJECT", "CLIENT", "PRODUCT", "DEPARTMENT"}
_ALLOWED_REQUESTED_FIELDS = {"DETAIL", "CONTACT", "POSITION", "MEMBERS", "RELATION"}
_RESOURCE_TOOL = {
    "NOTICE": "search_notices",
    "MAIL": "search_mail",
    "CALENDAR": "list_calendar_events",
}

class GroundedDelegationContractError(RuntimeError):
    code = "GROUNDED_DELEGATION_CONTRACT_INVALID"


class OrganizationReadDelegationInput(BaseModel):
    """Model interpretation proposal for one Organization Context read.

    No stable entity ID, Tool name, authorization identity, or execution evidence is accepted from
    the model. Stable identity may only be supplied by Runtime from SESSION_FOCUS after admission.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_id: Literal["organization-context-read-v1"] = "organization-context-read-v1"
    side_effect: Literal["READ"] = "READ"
    intent_kind: Literal[
        "ENTITY_DETAIL_LOOKUP",
        "ENTITY_FIELD_LOOKUP",
        "ENTITY_LIST",
    ]
    preferred_operation: Literal["RESOLVE", "SEARCH", "GET"]
    target_expression: str | None = Field(default=None, max_length=500)
    entity_type_hints: tuple[str, ...] = Field(default=(), max_length=4)
    requested_fields: tuple[str, ...] = Field(default=("DETAIL",), min_length=1, max_length=4)
    context_reference_mode: Literal["NONE", "SESSION_FOCUS"] = "NONE"

    @field_validator("target_expression")
    @classmethod
    def _normalize_target(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None

    @field_validator("entity_type_hints")
    @classmethod
    def _entity_types(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)) or any(item not in _ALLOWED_ENTITY_TYPES for item in value):
            raise ValueError("Unsupported or duplicate entity type hint")
        return value

    @field_validator("requested_fields")
    @classmethod
    def _requested_fields(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)) or any(item not in _ALLOWED_REQUESTED_FIELDS for item in value):
            raise ValueError("Unsupported or duplicate requested field")
        return value


class GroupwareReadDelegationInput(BaseModel):
    """Model interpretation proposal for one read-only Groupware resource."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_id: Literal["groupware-read-v1"] = "groupware-read-v1"
    side_effect: Literal["READ"] = "READ"
    resource_kind: Literal["NOTICE", "MAIL", "CALENDAR"]
    context_reference_mode: Literal["NONE", "SESSION_FOCUS"] = "NONE"


class GroundedDelegationAdmission:
    def __init__(self, project_root: str) -> None:
        self._organization = OrganizationContextReadCatalog(project_root)
        self._groupware = GroupwareReadCatalog(project_root)

    def admit_organization(
        self,
        *,
        raw: dict[str, Any],
        user_utterance: str,
        delegated_identity: DelegatedMCPIdentity | None,
        session_focus: SessionContextFocusRecord | None,
        parent_side_effect: str = "NONE",
    ) -> str:
        self._require_parent_read_admission(parent_side_effect)
        proposal = OrganizationReadDelegationInput.model_validate(raw)
        if delegated_identity is None:
            raise GroundedDelegationContractError("Organization read requires delegated identity")
        if self._organization.readiness(delegated_identity).state is not OrganizationContextReadState.READY:
            raise GroundedDelegationContractError("Organization read capability is not READY")

        target_expression = proposal.target_expression
        entity_types = proposal.entity_type_hints
        operation = OrganizationContextPreferredOperation(proposal.preferred_operation)
        pattern_id = "grounded-llm-organization-read-v1"

        if proposal.context_reference_mode == "SESSION_FOCUS":
            active = self._resolved_focus(session_focus)
            if operation is not OrganizationContextPreferredOperation.GET:
                raise GroundedDelegationContractError("SESSION_FOCUS Organization read requires GET")
            target_expression = active.entity_id
            entity_types = (active.entity_type,)
            pattern_id = "grounded-llm-session-focus-organization-read-v1"
        else:
            if operation is OrganizationContextPreferredOperation.GET:
                raise GroundedDelegationContractError("GET cannot accept a model-supplied stable identity")
            if target_expression is None:
                raise GroundedDelegationContractError("Organization RESOLVE/SEARCH requires a target expression")

        hint = OrganizationContextRequestHint(
            pattern_id=pattern_id,
            intent=proposal.intent_kind,
            target_expression=target_expression or "",
            entity_type_hints=entity_types,
            requested_fields=proposal.requested_fields,
            preferred_operation=operation,
        )
        context: dict[str, object] = {
            "schema_version": "okcanvas-assistant-routing-context-v2",
            "request_class": "SEARCH_KNOWLEDGE",
            "side_effect": "READ",
            "status": "EXECUTABLE",
            "required_capabilities": [self._organization.policy.capability_id],
            "matched_rule_id": pattern_id,
            "selected_agent_definition_id": _ROOT_AGENT_ID,
            "organization_context_request_hint": hint.to_public_dict(),
            "organization_context_request_hint_rules": {
                "routing_only": True,
                "not_entity_evidence": True,
                "stable_id_injected_only_from_runtime_session_focus": True,
                "tool_result_remains_authoritative": True,
            },
            "organization_context_read_policy": {
                "policy_id": self._organization.policy.policy_id,
                "version": self._organization.policy.version,
                "allowed_tools": list(self._organization.policy.allowed_tools),
                "max_results": self._organization.policy.max_results,
                "production_sot": "DATABASE",
                "write_enabled": False,
                "delegated_identity_required": True,
            },
            "grounded_delegation_admission": {
                "schema_version": "okcanvas-grounded-delegation-admission-v1",
                "capability_id": self._organization.policy.capability_id,
                "side_effect": "READ",
                "stable_ids_from_model_accepted": False,
                "admitted": True,
            },
        }
        return self._envelope(context, user_utterance)

    def admit_groupware(
        self,
        *,
        raw: dict[str, Any],
        user_utterance: str,
        delegated_identity: DelegatedMCPIdentity | None,
        session_focus: SessionContextFocusRecord | None,
        parent_side_effect: str = "NONE",
    ) -> str:
        self._require_parent_read_admission(parent_side_effect)
        proposal = GroupwareReadDelegationInput.model_validate(raw)
        if delegated_identity is None:
            raise GroundedDelegationContractError("Groupware read requires delegated identity")
        if self._groupware.readiness(delegated_identity).state is not GroupwareReadState.READY:
            raise GroundedDelegationContractError("Groupware read capability is not READY")
        tool_name = _RESOURCE_TOOL[proposal.resource_kind]
        context_filter: GroupwareContextFilterHint | None = None
        if proposal.context_reference_mode == "SESSION_FOCUS":
            active = self._resolved_focus(session_focus)
            if active.entity_type not in _GROUPWARE_CONTEXT_ENTITY_TYPES:
                raise GroundedDelegationContractError("Session focus cannot be a Groupware context filter")
            context_filter = GroupwareContextFilterHint(
                pattern_id="grounded-llm-session-focus-groupware-read-v1",
                resource_kind=proposal.resource_kind,
                tool_name=tool_name,
                entity_type=active.entity_type,
                entity_id=active.entity_id,
                label=active.label,
                qualifiers=active.qualifiers,
                catalog_revision=session_focus.catalog_revision if session_focus is not None else None,
                max_results=min(self._groupware.policy.max_results, 20),
            )
        context: dict[str, object] = {
            "schema_version": "okcanvas-assistant-routing-context-v2",
            "request_class": "READ_SYSTEM",
            "side_effect": "READ",
            "status": "EXECUTABLE",
            "required_capabilities": [self._groupware.policy.capability_id],
            "matched_rule_id": "grounded-llm-groupware-read-v1",
            "selected_agent_definition_id": _ROOT_AGENT_ID,
            "groupware_read_policy": {
                "policy_id": self._groupware.policy.policy_id,
                "version": self._groupware.policy.version,
                "allowed_tools": list(self._groupware.policy.allowed_tools),
                "max_results": self._groupware.policy.max_results,
                "write_enabled": False,
                "delegated_identity_required": True,
            },
            "groupware_operation_hint": {
                "schema_version": "okcanvas-groupware-operation-hint-v1",
                "resource_kind": proposal.resource_kind,
                "tool_name": tool_name,
                "routing_only": True,
            },
            "grounded_delegation_admission": {
                "schema_version": "okcanvas-grounded-delegation-admission-v1",
                "capability_id": self._groupware.policy.capability_id,
                "side_effect": "READ",
                "stable_ids_from_model_accepted": False,
                "admitted": True,
            },
        }
        if context_filter is not None:
            context["groupware_context_filter"] = context_filter.to_public_dict()
            context["groupware_context_filter_rules"] = {
                "routing_only": True,
                "stable_entity_from_prior_tool_evidence": True,
                "exact_tool_name_required": True,
                "exact_entity_type_and_id_must_be_forwarded": True,
                "tool_result_must_confirm_applied_filter": True,
                "returned_records_must_carry_exact_context_ref": True,
                "canonical_context_filter_arguments_only": True,
                "search_query_must_be_empty": True,
                "calendar_time_range_must_be_omitted": True,
                "limit_must_equal": context_filter.max_results,
                "do_not_fallback_to_label_search": True,
            }
        return self._envelope(context, user_utterance)

    @staticmethod
    def _require_parent_read_admission(parent_side_effect: str) -> None:
        if parent_side_effect not in {"NONE", "READ"}:
            raise GroundedDelegationContractError(
                "Product-owned non-read side-effect boundary forbids read-child delegation"
            )

    @staticmethod
    def _resolved_focus(session_focus: SessionContextFocusRecord | None):
        if (
            session_focus is None
            or session_focus.state is not SessionContextFocusState.RESOLVED
            or session_focus.active_entity is None
        ):
            raise GroundedDelegationContractError("SESSION_FOCUS requires one resolved active entity")
        return session_focus.active_entity

    @staticmethod
    def _envelope(context: dict[str, object], user_utterance: str) -> str:
        if not user_utterance.strip():
            raise GroundedDelegationContractError("Grounded delegation user utterance is empty")
        return (
            "OKCANVAS ROUTING CONTEXT (product-owned, immutable):\n"
            + json.dumps(context, ensure_ascii=False, sort_keys=True)
            + "\n\nUSER REQUEST:\n"
            + user_utterance.strip()
        )
