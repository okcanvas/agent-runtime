from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from okcanvas_agent_runtime.application.organization_context import OrganizationContextSearchResult


class AssistantRouteStatus(StrEnum):
    EXECUTABLE = "EXECUTABLE"
    PROPOSAL_ONLY = "PROPOSAL_ONLY"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    NO_MATCH = "NO_MATCH"
    AMBIGUOUS = "AMBIGUOUS"


class CapabilityAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    DISABLED = "DISABLED"


class OrganizationContextPreferredOperation(StrEnum):
    RESOLVE = "RESOLVE"
    SEARCH = "SEARCH"
    GET = "GET"


@dataclass(frozen=True)
class OrganizationContextRelationTraversalHint:
    source_entity_type: str
    source_entity_id: str
    relation_type: str
    direction: str
    result_entity_types: tuple[str, ...]
    max_results: int = 20

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-organization-context-relation-traversal-hint-v1",
            "source_entity_type": self.source_entity_type,
            "source_entity_id": self.source_entity_id,
            "relation_type": self.relation_type,
            "direction": self.direction,
            "result_entity_types": list(self.result_entity_types),
            "max_results": self.max_results,
        }


@dataclass(frozen=True)
class OrganizationContextRequestHint:
    pattern_id: str
    intent: str
    target_expression: str
    entity_type_hints: tuple[str, ...]
    requested_fields: tuple[str, ...]
    preferred_operation: OrganizationContextPreferredOperation
    relation_traversal: OrganizationContextRelationTraversalHint | None = None

    def to_public_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": "okcanvas-organization-context-request-hint-v1",
            "pattern_id": self.pattern_id,
            "intent": self.intent,
            "target_expression": self.target_expression,
            "entity_type_hints": list(self.entity_type_hints),
            "requested_fields": list(self.requested_fields),
            "preferred_operation": self.preferred_operation.value,
        }
        if self.relation_traversal is not None:
            payload["relation_traversal"] = self.relation_traversal.to_public_dict()
        return payload




@dataclass(frozen=True)
class GroupwareContextFilterHint:
    pattern_id: str
    resource_kind: str
    tool_name: str
    entity_type: str
    entity_id: str
    label: str
    qualifiers: tuple[str, ...] = ()
    catalog_revision: int | None = None
    max_results: int = 20

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-groupware-context-filter-hint-v1",
            "pattern_id": self.pattern_id,
            "resource_kind": self.resource_kind,
            "tool_name": self.tool_name,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "label": self.label,
            "qualifiers": list(self.qualifiers),
            "catalog_revision": self.catalog_revision,
            "max_results": self.max_results,
        }


@dataclass(frozen=True)
class GroundedSessionRouteShadow:
    selected_agent_id: str
    matched_rule_id: str = "session-bound-grounded-interpretation-shadow-v1"
    reasons: tuple[str, ...] = (
        "bound-session-root-retained",
        "semantic-request-class-deferred-to-llm-shadow",
        "semantic-side-effect-deferred-to-llm-shadow",
        "legacy-route-remains-authoritative",
    )

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-assistant-route-v3",
            "interpretation_mode": "LLM_GROUNDED",
            "request_class": None,
            "side_effect": None,
            "status": "EXECUTABLE",
            "selected_agent_definition_id": self.selected_agent_id,
            "executable_now": True,
            "matched_rule_id": self.matched_rule_id,
            "reasons": list(self.reasons),
            "authoritative": False,
            "legacy_authoritative_route_schema": "okcanvas-assistant-route-v2",
        }


@dataclass(frozen=True)
class AssistantCapability:
    capability_id: str
    availability: CapabilityAvailability
    selected_agent_id: str | None
    side_effect: str

    def to_public_dict(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id,
            "availability": self.availability.value,
            "selected_agent_id": self.selected_agent_id,
            "side_effect": self.side_effect,
        }


@dataclass(frozen=True)
class AssistantRouteDecision:
    request_class: str
    side_effect: str
    status: AssistantRouteStatus
    selected_agent_id: str | None
    required_capabilities: tuple[AssistantCapability, ...]
    matched_rule_id: str
    reasons: tuple[str, ...]
    policy_id: str
    policy_version: str
    policy_sha256: str
    grounding: OrganizationContextSearchResult | None = None
    organization_context_request_hint: OrganizationContextRequestHint | None = None
    groupware_context_filter: GroupwareContextFilterHint | None = None
    grounded_interpretation_shadow: GroundedSessionRouteShadow | None = None

    @property
    def executable_now(self) -> bool:
        return self.status in {
            AssistantRouteStatus.EXECUTABLE,
            AssistantRouteStatus.PROPOSAL_ONLY,
        } and self.selected_agent_id is not None

    @property
    def grounding_state(self) -> str:
        if self.grounding is None:
            return "NOT_APPLICABLE"
        if self.grounding.catalog_state.value == "EMPTY":
            return "NOT_CONFIGURED"
        if self.grounding.ambiguous:
            return "AMBIGUOUS"
        if not self.grounding.matches:
            return "NO_MATCH"
        return "MATCHED"

    def to_public_dict(self) -> dict[str, object]:
        grounding = self.grounding
        return {
            "schema_version": "okcanvas-assistant-route-v2",
            "request_class": self.request_class,
            "side_effect": self.side_effect,
            "status": self.status.value,
            "selected_agent_definition_id": self.selected_agent_id,
            "executable_now": self.executable_now,
            "required_capabilities": [item.to_public_dict() for item in self.required_capabilities],
            "matched_rule_id": self.matched_rule_id,
            "reasons": list(self.reasons),
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_sha256": self.policy_sha256,
            "grounding_state": self.grounding_state,
            "grounding_catalog_id": grounding.catalog_id if grounding is not None else None,
            "grounding_catalog_version": grounding.catalog_version if grounding is not None else None,
            "grounding_effective_at": grounding.effective_at if grounding is not None else None,
            "grounding": [item.to_public_dict() for item in grounding.matches] if grounding is not None else [],
            "organization_context_request_hint": (
                self.organization_context_request_hint.to_public_dict()
                if self.organization_context_request_hint is not None
                else None
            ),
            "groupware_context_filter": (
                self.groupware_context_filter.to_public_dict()
                if self.groupware_context_filter is not None
                else None
            ),
            "grounded_interpretation_shadow": (
                self.grounded_interpretation_shadow.to_public_dict()
                if self.grounded_interpretation_shadow is not None
                else None
            ),
        }
