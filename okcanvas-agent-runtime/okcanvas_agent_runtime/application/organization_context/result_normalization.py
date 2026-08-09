from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from okcanvas_agent_runtime.application.execution.nested_output import NestedResultNormalization
from okcanvas_agent_runtime.application.organization_context.request_execution import (
    organization_context_request_hint,
)
from okcanvas_agent_runtime.domain.sessions.context_focus import (
    SessionContextEntityRef, SessionContextFocusObservation, SessionContextFocusState,
)
from okcanvas_agent_runtime.core.contracts import (
    OrganizationContextReadCitation,
    OrganizationContextReadResult,
    OrganizationContextReadStatus,
)

_ALLOWED_TOOLS = frozenset(
    {
        "resolve_organization_context",
        "search_organization_context",
        "get_organization_entity",
    }
)
_PREFERRED_OPERATION_TOOL = {
    "RESOLVE": "resolve_organization_context",
    "SEARCH": "search_organization_context",
    "GET": "get_organization_entity",
}
_ALLOWED_RELATION_TRAVERSALS = {
    ("EMPLOYEE_MANAGES_PRODUCT", "OUTBOUND", "EMPLOYEE"): ("PRODUCT",),
    ("EMPLOYEE_MANAGES_CLIENT", "OUTBOUND", "EMPLOYEE"): ("CLIENT",),
    ("EMPLOYEE_MANAGES_PROJECT", "OUTBOUND", "EMPLOYEE"): ("PROJECT",),
    ("EMPLOYEE_BELONGS_TO_DEPARTMENT", "OUTBOUND", "EMPLOYEE"): ("DEPARTMENT",),
    ("EMPLOYEE_REPORTS_TO_EMPLOYEE", "OUTBOUND", "EMPLOYEE"): ("EMPLOYEE",),
    ("PRODUCT_OWNED_BY_DEPARTMENT", "OUTBOUND", "PRODUCT"): ("DEPARTMENT",),
    ("CLIENT_USES_PRODUCT", "OUTBOUND", "CLIENT"): ("PRODUCT",),
    ("CLIENT_USES_PRODUCT", "INBOUND", "PRODUCT"): ("CLIENT",),
    ("PROJECT_FOR_CLIENT", "OUTBOUND", "PROJECT"): ("CLIENT",),
    ("PROJECT_FOR_CLIENT", "INBOUND", "CLIENT"): ("PROJECT",),
}


class OrganizationContextNormalizationError(ValueError):
    def __init__(self, safe_category: str, message: str) -> None:
        super().__init__(message)
        self.safe_category = safe_category


def _json_objects(value: object) -> tuple[dict[str, Any], ...]:
    """Decode the exact OpenAI Agents 0.19.0 MCP ToolOutput protocol.

    MCP Tool outputs are model-visible text dictionaries (or a list of them)
    when ``use_structured_content`` is disabled. Direct JSON strings and the
    structured-content wrapper remain supported for the configured SDK mode.
    No value is inferred from prompts, Tool arguments, or aliases.
    """

    if isinstance(value, BaseModel):
        return _json_objects(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        mapped = dict(value)
        if mapped.get("type") == "text" and isinstance(mapped.get("text"), str):
            return _json_objects(mapped["text"])
        structured = mapped.get("structuredContent")
        if isinstance(structured, Mapping):
            return _json_objects(dict(structured))
        output = mapped.get("output")
        if output is not None and output is not value:
            decoded = _json_objects(output)
            if decoded:
                return decoded
        content = mapped.get("content")
        if isinstance(content, Sequence) and not isinstance(content, (str, bytes, bytearray)):
            decoded = tuple(
                item
                for content_item in content
                for item in _json_objects(content_item)
            )
            if decoded:
                return decoded
        return (mapped,)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(item for part in value for item in _json_objects(part))
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return ()
        return _json_objects(parsed)
    text = getattr(value, "text", None)
    if getattr(value, "type", None) == "text" and isinstance(text, str):
        return _json_objects(text)
    return ()


def _item_output(item: object) -> object | None:
    output = getattr(item, "output", None)
    if output is not None:
        return output
    raw = getattr(item, "raw_item", None)
    if isinstance(raw, Mapping):
        return raw.get("output", raw)
    if raw is not None:
        nested = getattr(raw, "output", None)
        return nested if nested is not None else raw
    return None


def _observed_tool_payload(items: Iterable[object]) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for item in items:
        decoded = _json_objects(_item_output(item))
        for payload in decoded:
            tool_name = payload.get("tool_name")
            if isinstance(tool_name, str) and tool_name in _ALLOWED_TOOLS:
                matches.append(payload)
    if not matches:
        raise OrganizationContextNormalizationError(
            "ALLOWLISTED_MCP_TOOL_RESULT_NOT_OBSERVED",
            "Organization Context normalization did not observe an allowlisted MCP Tool result",
        )
    if len(matches) != 1:
        raise OrganizationContextNormalizationError(
            "MULTIPLE_ALLOWLISTED_MCP_TOOL_RESULTS_OBSERVED",
            "Organization Context normalization observed multiple allowlisted MCP Tool results",
        )
    return matches[0]


_ID_ENTITY_TYPE = {
    "employee_id": "EMPLOYEE",
    "department_id": "DEPARTMENT",
    "position_id": "POSITION",
    "product_id": "PRODUCT",
    "client_id": "CLIENT",
    "project_id": "PROJECT",
    "system_id": "SYSTEM",
    "capability_id": "CAPABILITY",
    "term_id": "TERM",
}
_ALLOWED_ENTITY_TYPES = frozenset(_ID_ENTITY_TYPE.values())


def _stable_entity(record: dict[str, Any]) -> tuple[str, str] | None:
    generic_id = record.get("entity_id")
    generic_type = record.get("entity_type")
    if (
        isinstance(generic_id, str)
        and generic_id.strip()
        and isinstance(generic_type, str)
        and generic_type.strip().upper() in _ALLOWED_ENTITY_TYPES
    ):
        return generic_type.strip().upper(), generic_id.strip()
    for key, entity_type in _ID_ENTITY_TYPE.items():
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return entity_type, value.strip()
    nested = record.get("record")
    return _stable_entity(nested) if isinstance(nested, dict) else None


def _stable_id(record: dict[str, Any]) -> str | None:
    entity = _stable_entity(record)
    return entity[1] if entity is not None else None


def _display_name(record: dict[str, Any], stable_id: str) -> str:
    for key in ("display_name", "canonical_name", "name", "legal_name"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    nested = record.get("record")
    if isinstance(nested, dict):
        for key in ("canonical_name", "name", "display_name", "legal_name"):
            value = nested.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return stable_id


def _candidate_context(record: dict[str, Any]) -> tuple[str | None, tuple[str, ...]]:
    context = record.get("context")
    if not isinstance(context, dict):
        return None, ()
    department = context.get("department_name")
    positions = context.get("positions")
    return (
        department.strip() if isinstance(department, str) and department.strip() else None,
        tuple(
            value.strip()
            for value in positions
            if isinstance(value, str) and value.strip()
        )
        if isinstance(positions, list)
        else (),
    )


def _session_focus_observation(
    *,
    records: list[dict[str, Any]],
    state: SessionContextFocusState,
    catalog_revision: int | None,
) -> dict[str, object]:
    candidates: list[SessionContextEntityRef] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        identity = _stable_entity(record)
        if identity is None or identity in seen:
            continue
        seen.add(identity)
        entity_type, stable_id = identity
        department, positions = _candidate_context(record)
        qualifiers = tuple(value for value in (department, *positions) if value)[:8]
        candidates.append(
            SessionContextEntityRef(
                entity_type=entity_type,
                entity_id=stable_id,
                label=_display_name(record, stable_id)[:300],
                qualifiers=qualifiers,
            )
        )
        if len(candidates) >= 20:
            break
    effective_state = state
    if not candidates:
        effective_state = SessionContextFocusState.EMPTY
    elif state is not SessionContextFocusState.AMBIGUOUS:
        effective_state = (
            SessionContextFocusState.RESOLVED
            if len(candidates) == 1
            else SessionContextFocusState.MULTIPLE
        )
    observation = SessionContextFocusObservation(
        domain="ORGANIZATION_CONTEXT",
        state=effective_state,
        candidates=tuple(candidates),
        catalog_revision=catalog_revision,
    )
    return observation.to_public_dict()


def _citations(records: list[dict[str, Any]]) -> list[OrganizationContextReadCitation]:
    citations: list[OrganizationContextReadCitation] = []
    seen: set[str] = set()
    for record in records[:30]:
        stable_id = _stable_id(record)
        if stable_id is None or stable_id in seen:
            continue
        seen.add(stable_id)
        citations.append(
            OrganizationContextReadCitation(
                label=_display_name(record, stable_id)[:300],
                reference=stable_id[:500],
            )
        )
    return citations


def _relation_traversal_hint(hint: dict[str, Any]) -> dict[str, Any] | None:
    raw = hint.get("relation_traversal")
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) != {
        "schema_version", "source_entity_type", "source_entity_id", "relation_type",
        "direction", "result_entity_types", "max_results",
    }:
        raise OrganizationContextNormalizationError(
            "RELATION_TRAVERSAL_HINT_INVALID",
            "Organization Context relation traversal hint is malformed",
        )
    if raw.get("schema_version") != "okcanvas-organization-context-relation-traversal-hint-v1":
        raise OrganizationContextNormalizationError(
            "RELATION_TRAVERSAL_HINT_INVALID",
            "Organization Context relation traversal hint schema is unsupported",
        )
    source_type = raw.get("source_entity_type")
    source_id = raw.get("source_entity_id")
    relation_type = raw.get("relation_type")
    direction = raw.get("direction")
    result_types = raw.get("result_entity_types")
    max_results = raw.get("max_results")
    if (
        not isinstance(source_type, str) or source_type not in _ALLOWED_ENTITY_TYPES
        or not isinstance(source_id, str) or not source_id.strip()
        or not isinstance(relation_type, str) or not relation_type.strip()
        or direction not in {"OUTBOUND", "INBOUND"}
        or not isinstance(result_types, list) or not result_types
        or any(not isinstance(item, str) or item not in _ALLOWED_ENTITY_TYPES for item in result_types)
        or not isinstance(max_results, int) or isinstance(max_results, bool) or not 1 <= max_results <= 20
    ):
        raise OrganizationContextNormalizationError(
            "RELATION_TRAVERSAL_HINT_INVALID",
            "Organization Context relation traversal hint contains invalid bounded values",
        )
    expected = _ALLOWED_RELATION_TRAVERSALS.get((relation_type, direction, source_type))
    if expected is None or tuple(result_types) != expected:
        raise OrganizationContextNormalizationError(
            "RELATION_TRAVERSAL_HINT_NOT_ALLOWED",
            "Organization Context relation traversal is outside the bounded Product relation contract",
        )
    target = hint.get("target_expression")
    hinted_types = hint.get("entity_type_hints")
    if target != source_id or hinted_types != [source_type]:
        raise OrganizationContextNormalizationError(
            "RELATION_TRAVERSAL_SOURCE_MISMATCH",
            "Relation traversal source disagrees with the immutable GET routing hint",
        )
    return {
        "source_entity_type": source_type,
        "source_entity_id": source_id.strip(),
        "relation_type": relation_type,
        "direction": direction,
        "result_entity_types": tuple(result_types),
        "max_results": max_results,
    }


def _relation_projected_records(
    source_record: dict[str, Any], relation_hint: dict[str, Any]
) -> list[dict[str, Any]]:
    relations = source_record.get("relations")
    relation_count = source_record.get("relation_count")
    returned_count = source_record.get("relations_returned_count")
    truncated = source_record.get("relations_truncated")
    if (
        not isinstance(relations, list)
        or not isinstance(relation_count, int) or isinstance(relation_count, bool) or relation_count < 0
        or not isinstance(returned_count, int) or isinstance(returned_count, bool) or returned_count < 0
        or not isinstance(truncated, bool)
        or returned_count != len(relations)
        or relation_count < returned_count
    ):
        raise OrganizationContextNormalizationError(
            "RELATION_COMPLETENESS_EVIDENCE_MISSING",
            "GET Organization Context evidence lacks valid relationship completeness metadata",
        )
    if truncated or relation_count != returned_count:
        raise OrganizationContextNormalizationError(
            "RELATION_EVIDENCE_TRUNCATED",
            "Relationship-aware follow-up refuses incomplete GET relationship evidence",
        )
    projected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        if (
            relation.get("relation_type") != relation_hint["relation_type"]
            or relation.get("direction") != relation_hint["direction"]
        ):
            continue
        related = relation.get("related_entity")
        if not isinstance(related, dict):
            raise OrganizationContextNormalizationError(
                "RELATION_STABLE_ENTITY_EVIDENCE_MISSING",
                "Matched Organization Context relationship lacks a related stable entity",
            )
        identity = _stable_entity(related)
        if identity is None:
            raise OrganizationContextNormalizationError(
                "RELATION_STABLE_ENTITY_EVIDENCE_MISSING",
                "Matched Organization Context relationship lacks a related stable entity identity",
            )
        entity_type, entity_id = identity
        if entity_type not in relation_hint["result_entity_types"]:
            raise OrganizationContextNormalizationError(
                "RELATION_TARGET_TYPE_MISMATCH",
                "Matched Organization Context relationship target type disagrees with the bounded relation contract",
            )
        key = (entity_type, entity_id)
        if key in seen:
            continue
        seen.add(key)
        normalized = dict(related)
        normalized["entity_type"] = entity_type
        normalized["entity_id"] = entity_id
        projected.append(normalized)
    if len(projected) > relation_hint["max_results"]:
        raise OrganizationContextNormalizationError(
            "RELATION_RESULT_BOUND_EXCEEDED",
            "Relationship-aware follow-up exceeds the bounded related-entity result limit",
        )
    return projected


def _validate_routing_hint_evidence(
    *,
    request: str,
    tool_name: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    hint = organization_context_request_hint(request)
    preferred = hint.get("preferred_operation")
    if isinstance(preferred, str):
        expected_tool = _PREFERRED_OPERATION_TOOL.get(preferred)
        if expected_tool is None or tool_name != expected_tool:
            raise OrganizationContextNormalizationError(
                "ROUTING_HINT_TOOL_MISMATCH",
                "Organization Context Tool result disagrees with the immutable routing operation",
            )
    if preferred != "GET":
        return hint

    target = hint.get("target_expression")
    types = hint.get("entity_type_hints")
    if not isinstance(target, str) or not target.strip():
        raise OrganizationContextNormalizationError(
            "ROUTING_HINT_STABLE_ENTITY_INVALID",
            "GET routing requires one bounded stable entity ID",
        )
    allowed_types = (
        tuple(item for item in types if isinstance(item, str) and item in _ALLOWED_ENTITY_TYPES)
        if isinstance(types, list)
        else ()
    )
    if isinstance(types, list) and len(allowed_types) != len(types):
        raise OrganizationContextNormalizationError(
            "ROUTING_HINT_STABLE_ENTITY_INVALID",
            "GET routing contains an unsupported entity type",
        )
    if len(records) != 1:
        raise OrganizationContextNormalizationError(
            "GET_STABLE_ENTITY_CARDINALITY_MISMATCH",
            "GET Organization Context evidence must return exactly one entity for a Session-focus follow-up",
        )
    identity = _stable_entity(records[0])
    if identity is None:
        raise OrganizationContextNormalizationError(
            "GET_STABLE_ENTITY_EVIDENCE_MISSING",
            "GET Organization Context evidence lacks a stable entity identity",
        )
    observed_type, observed_id = identity
    if observed_id != target.strip() or (allowed_types and observed_type not in allowed_types):
        raise OrganizationContextNormalizationError(
            "GET_STABLE_ENTITY_EVIDENCE_MISMATCH",
            "GET Organization Context evidence does not match the immutable Session focus",
        )
    relation_hint = _relation_traversal_hint(hint)
    if relation_hint is not None and (
        relation_hint["source_entity_type"] != observed_type
        or relation_hint["source_entity_id"] != observed_id
    ):
        raise OrganizationContextNormalizationError(
            "RELATION_TRAVERSAL_SOURCE_EVIDENCE_MISMATCH",
            "GET Organization Context evidence does not match the immutable relation source",
        )
    return hint


def _ambiguous_output(
    *, payload: dict[str, Any], records: list[dict[str, Any]], tool_name: str
) -> NestedResultNormalization:
    candidates: list[tuple[str, str, str | None, tuple[str, ...]]] = []
    seen: set[str] = set()
    for record in records:
        stable_id = _stable_id(record)
        if stable_id is None or stable_id in seen:
            continue
        seen.add(stable_id)
        department, positions = _candidate_context(record)
        candidates.append(
            (stable_id, _display_name(record, stable_id), department, positions)
        )
    if len(candidates) < 2:
        raise OrganizationContextNormalizationError(
            "AMBIGUOUS_STABLE_ID_EVIDENCE_INSUFFICIENT",
            "Ambiguous Organization Context evidence must contain at least two stable IDs",
        )
    candidates = candidates[:20]
    lines = [
        f"동명이인 후보가 {len(candidates)}명입니다. 한 사람으로 추측할 수 없습니다.",
        "부서·직책 또는 근거 ID로 대상을 지정해 주세요.",
    ]
    unverified: list[str] = []
    for stable_id, label, department, positions in candidates:
        context_parts = [value for value in (department, ", ".join(positions)) if value]
        context = " / ".join(context_parts) if context_parts else "추가 식별 정보 필요"
        lines.append(f"- {label} — {context} — {stable_id}")
        unverified.append(f"{label} | {context} | {stable_id}")
    revision = payload.get("catalog_revision")
    output = OrganizationContextReadResult(
        status=OrganizationContextReadStatus.NEEDS_CLARIFICATION,
        answer="\n".join(lines)[:8000],
        queried_operations=[tool_name],
        result_count=len(candidates),
        catalog_revision=revision if isinstance(revision, int) and revision >= 0 else None,
        citations=[
            OrganizationContextReadCitation(label=label[:300], reference=stable_id[:500])
            for stable_id, label, _department, _positions in candidates
        ],
        unverified=unverified[:50],
    )
    focus = _session_focus_observation(
        records=records,
        state=SessionContextFocusState.AMBIGUOUS,
        catalog_revision=output.catalog_revision,
    )
    return NestedResultNormalization(
        output=output,
        metadata={
            "strategy": "deterministic-ambiguous-tool-evidence-v1",
            "tool_name": tool_name,
            "ambiguous": True,
            "candidate_count": len(candidates),
            "clarification_applied": True,
            "model_calls_added": 0,
            "tool_reexecuted": False,
            "model_output_persisted": False,
            "tool_result_persisted": False,
            "session_context_focus": focus,
        },
    )


def normalize_organization_context_nested_result(
    *, result: Any, output: BaseModel, request: str
) -> NestedResultNormalization:
    if not isinstance(output, OrganizationContextReadResult):
        raise TypeError("Organization Context nested normalizer received the wrong output type")
    payload = _observed_tool_payload(tuple(getattr(result, "new_items", ()) or ()))
    tool_name = payload.get("tool_name")
    if not isinstance(tool_name, str) or tool_name not in _ALLOWED_TOOLS:
        raise OrganizationContextNormalizationError(
            "NON_ALLOWLISTED_MCP_TOOL_RESULT",
            "Organization Context Tool result used a non-allowlisted Tool",
        )
    raw_records = payload.get("records")
    records = [item for item in raw_records if isinstance(item, dict)] if isinstance(raw_records, list) else []
    hint = _validate_routing_hint_evidence(request=request, tool_name=tool_name, records=records)
    ambiguous = payload.get("ambiguous") is True
    if ambiguous:
        return _ambiguous_output(payload=payload, records=records, tool_name=tool_name)

    # The successful Tool result is the authority for provenance fields. Model wording is retained.
    revision = payload.get("catalog_revision")
    relation_hint = _relation_traversal_hint(hint)
    focus_records = records
    strategy = "tool-evidence-provenance-alignment-v1"
    if relation_hint is not None:
        focus_records = _relation_projected_records(records[0], relation_hint)
        strategy = "tool-evidence-relation-projection-v1"
    citations = _citations(focus_records)
    normalized = OrganizationContextReadResult(
        status=OrganizationContextReadStatus.ANSWERED,
        answer=output.answer,
        queried_operations=[tool_name],
        result_count=len(citations),
        catalog_revision=revision if isinstance(revision, int) and revision >= 0 else None,
        citations=citations,
        unverified=output.unverified,
    )
    focus = _session_focus_observation(
        records=focus_records,
        state=SessionContextFocusState.RESOLVED,
        catalog_revision=normalized.catalog_revision,
    )
    metadata = {
        "strategy": strategy,
        "tool_name": tool_name,
        "ambiguous": False,
        "candidate_count": len(focus_records),
        "clarification_applied": False,
        "requested_field_count": len(hint.get("requested_fields") or []),
        "model_calls_added": 0,
        "tool_reexecuted": False,
        "model_output_persisted": False,
        "tool_result_persisted": False,
        "session_context_focus": focus,
    }
    if relation_hint is not None:
        metadata.update({
            "relation_type": relation_hint["relation_type"],
            "relation_direction": relation_hint["direction"],
            "relation_source_entity_id": relation_hint["source_entity_id"],
            "relation_projected_count": len(focus_records),
        })
    return NestedResultNormalization(output=normalized, metadata=metadata)
