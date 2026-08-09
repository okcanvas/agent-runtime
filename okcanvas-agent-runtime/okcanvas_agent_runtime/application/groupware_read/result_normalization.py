from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from okcanvas_agent_runtime.application.execution.nested_output import NestedResultNormalization
from okcanvas_agent_runtime.core.contracts import (
    GroupwareReadCitation, GroupwareReadResult, GroupwareReadStatus,
)
from okcanvas_agent_runtime.domain.sessions.context_focus import (
    SessionContextEntityRef, SessionContextFocusObservation, SessionContextFocusState,
)
from .request_execution import groupware_context_filter, groupware_operation_hint

_ALLOWED_TOOLS = {"search_notices", "search_mail", "list_calendar_events"}
_ALLOWED_ENTITY_TYPES = {"EMPLOYEE", "PROJECT", "CLIENT", "PRODUCT", "DEPARTMENT"}


class GroupwareNormalizationError(ValueError):
    def __init__(self, safe_category: str, message: str) -> None:
        super().__init__(message)
        self.safe_category = safe_category


def _json_objects(value: object) -> tuple[dict[str, Any], ...]:
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
            decoded = tuple(item for part in content for item in _json_objects(part))
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


def _observed_tool_payloads(result: Any) -> tuple[dict[str, Any], ...]:
    matches: list[dict[str, Any]] = []
    for item in tuple(getattr(result, "new_items", ()) or ()):
        for payload in _json_objects(_item_output(item)):
            if payload.get("tool_name") in _ALLOWED_TOOLS:
                matches.append(payload)
    return tuple(matches)


def _validated_context_hint(request: str) -> dict[str, Any] | None:
    hint = groupware_context_filter(request)
    if not hint:
        return None
    expected = {
        "schema_version","pattern_id","resource_kind","tool_name","entity_type",
        "entity_id","label","qualifiers","catalog_revision","max_results",
    }
    if set(hint) != expected or hint.get("schema_version") != "okcanvas-groupware-context-filter-hint-v1":
        raise GroupwareNormalizationError("GROUPWARE_CONTEXT_FILTER_INVALID", "Groupware context filter contract is invalid")
    if hint.get("tool_name") not in _ALLOWED_TOOLS or hint.get("entity_type") not in _ALLOWED_ENTITY_TYPES:
        raise GroupwareNormalizationError("GROUPWARE_CONTEXT_FILTER_INVALID", "Groupware context filter identity or Tool is invalid")
    entity_id=hint.get("entity_id")
    label=hint.get("label")
    qualifiers=hint.get("qualifiers")
    max_results=hint.get("max_results")
    if not isinstance(entity_id,str) or not entity_id.strip() or not isinstance(label,str) or not label.strip():
        raise GroupwareNormalizationError("GROUPWARE_CONTEXT_FILTER_INVALID", "Groupware context filter stable entity is invalid")
    if not isinstance(qualifiers,list) or any(not isinstance(x,str) for x in qualifiers):
        raise GroupwareNormalizationError("GROUPWARE_CONTEXT_FILTER_INVALID", "Groupware context filter qualifiers are invalid")
    if not isinstance(max_results,int) or isinstance(max_results,bool) or not 1 <= max_results <= 20:
        raise GroupwareNormalizationError("GROUPWARE_CONTEXT_FILTER_INVALID", "Groupware context filter max_results is invalid")
    return hint



def _validated_operation_hint(request: str) -> dict[str, Any] | None:
    hint = groupware_operation_hint(request)
    if not hint:
        return None
    tool_name = hint.get("tool_name")
    resource_kind = hint.get("resource_kind")
    expected = {"NOTICE": "search_notices", "MAIL": "search_mail", "CALENDAR": "list_calendar_events"}
    if not isinstance(resource_kind, str) or expected.get(resource_kind) != tool_name:
        raise GroupwareNormalizationError(
            "GROUPWARE_OPERATION_HINT_INVALID",
            "Grounded Groupware operation hint is invalid",
        )
    return hint

def _record_has_context_ref(record: dict[str, Any], expected: dict[str, str]) -> bool:
    refs=record.get("context_refs")
    if not isinstance(refs,list):
        return False
    return any(
        isinstance(item,dict)
        and item.get("entity_type") == expected["entity_type"]
        and item.get("entity_id") == expected["entity_id"]
        for item in refs
    )


def _citation(record: dict[str, Any]) -> GroupwareReadCitation | None:
    record_id=record.get("record_id")
    if not isinstance(record_id,str) or not record_id.strip():
        return None
    label=None
    for key in ("title","subject"):
        value=record.get(key)
        if isinstance(value,str) and value.strip():
            label=value.strip()
            break
    return GroupwareReadCitation(label=(label or record_id)[:300], reference=record_id[:500])


def normalize_groupware_nested_result(*, result: Any, output: BaseModel, request: str) -> NestedResultNormalization:
    if not isinstance(output, GroupwareReadResult):
        raise TypeError("Groupware nested normalizer received the wrong output type")
    hint=_validated_context_hint(request)
    operation_hint=_validated_operation_hint(request)
    if hint is None and operation_hint is None:
        return NestedResultNormalization(output=output, metadata={})
    observed=_observed_tool_payloads(result)
    if hint is None and operation_hint is not None:
        if len(observed) != 1:
            raise GroupwareNormalizationError(
                "GROUPWARE_OPERATION_TOOL_RESULT_CARDINALITY_MISMATCH",
                "Grounded Groupware read requires exactly one allowlisted MCP Tool result",
            )
        tool_name=observed[0].get("tool_name")
        if tool_name != operation_hint["tool_name"]:
            raise GroupwareNormalizationError(
                "GROUPWARE_OPERATION_TOOL_MISMATCH",
                "Groupware Tool result disagrees with the admitted operation",
            )
        return NestedResultNormalization(
            output=output,
            metadata={
                "strategy":"grounded-groupware-operation-admission-v1",
                "tool_name":tool_name,
                "context_filter_applied":False,
                "model_output_persisted":False,
                "tool_result_persisted":False,
            },
        )
    observed=_observed_tool_payloads(result)
    if len(observed) != 1:
        raise GroupwareNormalizationError(
            "GROUPWARE_CONTEXT_FILTER_TOOL_RESULT_CARDINALITY_MISMATCH",
            "Cross-domain Groupware follow-up requires exactly one allowlisted MCP Tool result",
        )
    payload=observed[0]
    tool_name=payload.get("tool_name")
    if tool_name != hint["tool_name"]:
        raise GroupwareNormalizationError("GROUPWARE_CONTEXT_FILTER_TOOL_MISMATCH", "Groupware Tool result disagrees with the immutable context filter")
    applied=payload.get("context_ref")
    expected_ref={"entity_type":hint["entity_type"],"entity_id":hint["entity_id"]}
    if not isinstance(applied,dict) or applied != expected_ref:
        raise GroupwareNormalizationError("GROUPWARE_CONTEXT_FILTER_NOT_APPLIED", "Groupware Tool did not apply the immutable stable context reference")
    raw_records=payload.get("records")
    records=[item for item in raw_records if isinstance(item,dict)] if isinstance(raw_records,list) else []
    if len(records) > hint["max_results"]:
        raise GroupwareNormalizationError("GROUPWARE_CONTEXT_FILTER_RESULT_BOUND_EXCEEDED", "Groupware context-filtered result exceeds the Product bound")
    if any(not _record_has_context_ref(record, expected_ref) for record in records):
        raise GroupwareNormalizationError("GROUPWARE_CONTEXT_FILTER_EVIDENCE_MISMATCH", "Returned Groupware record does not carry the immutable context reference")
    citations=[]
    for record in records:
        item=_citation(record)
        if item is not None:
            citations.append(item)
        if len(citations) >= 30:
            break
    normalized=GroupwareReadResult(
        status=GroupwareReadStatus.ANSWERED,
        answer=output.answer,
        queried_operations=[tool_name],
        result_count=len(records),
        citations=citations,
        unverified=output.unverified,
    )
    focus=SessionContextFocusObservation(
        domain="ORGANIZATION_CONTEXT",
        state=SessionContextFocusState.RESOLVED,
        candidates=(SessionContextEntityRef(
            entity_type=hint["entity_type"],entity_id=hint["entity_id"],
            label=hint["label"],qualifiers=tuple(hint["qualifiers"]),
        ),),
        catalog_revision=hint["catalog_revision"] if isinstance(hint["catalog_revision"],int) else None,
    )
    return NestedResultNormalization(
        output=normalized,
        metadata={
            "strategy":"groupware-cross-domain-stable-context-filter-v1",
            "tool_name":tool_name,
            "context_entity_type":hint["entity_type"],
            "context_entity_id":hint["entity_id"],
            "context_filter_applied":True,
            "context_filtered_record_count":len(records),
            "model_output_persisted":False,
            "tool_result_persisted":False,
            "session_context_focus":focus.to_public_dict(),
        },
    )
