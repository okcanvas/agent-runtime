from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from okcanvas_agent_runtime.application.execution.nested_output import NestedResultNormalization
from okcanvas_agent_runtime.application.organization_context.request_execution import (
    organization_context_request_hint,
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


def _stable_id(record: dict[str, Any]) -> str | None:
    for key in (
        "entity_id",
        "employee_id",
        "department_id",
        "position_id",
        "product_id",
        "client_id",
        "project_id",
        "system_id",
        "capability_id",
        "term_id",
    ):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    nested = record.get("record")
    return _stable_id(nested) if isinstance(nested, dict) else None


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
    candidates = candidates[:30]
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
    ambiguous = payload.get("ambiguous") is True
    if ambiguous:
        return _ambiguous_output(payload=payload, records=records, tool_name=tool_name)

    # The successful Tool result is the authority for provenance fields. Model wording is retained.
    revision = payload.get("catalog_revision")
    citations = _citations(records)
    normalized = OrganizationContextReadResult(
        status=OrganizationContextReadStatus.ANSWERED,
        answer=output.answer,
        queried_operations=[tool_name],
        result_count=len(citations),
        catalog_revision=revision if isinstance(revision, int) and revision >= 0 else None,
        citations=citations,
        unverified=output.unverified,
    )
    hint = organization_context_request_hint(request)
    return NestedResultNormalization(
        output=normalized,
        metadata={
            "strategy": "tool-evidence-provenance-alignment-v1",
            "tool_name": tool_name,
            "ambiguous": False,
            "candidate_count": len(records),
            "clarification_applied": False,
            "requested_field_count": len(hint.get("requested_fields") or []),
            "model_calls_added": 0,
            "tool_reexecuted": False,
            "model_output_persisted": False,
            "tool_result_persisted": False,
        },
    )
