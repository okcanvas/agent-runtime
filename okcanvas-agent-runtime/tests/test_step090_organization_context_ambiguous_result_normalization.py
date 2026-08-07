from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from okcanvas_agent_runtime.application.organization_context.result_normalization import (
    normalize_organization_context_nested_result,
)
from okcanvas_agent_runtime.application.execution.output_registry import resolve_output_contract
from okcanvas_agent_runtime.core.contracts import (
    OrganizationContextReadCitation,
    OrganizationContextReadResult,
    OrganizationContextReadStatus,
)


def _result(payload: dict[str, object]) -> SimpleNamespace:
    # Exact openai-agents 0.19.0 MCP ToolOutput shape when structured content is disabled.
    return SimpleNamespace(
        new_items=[
            SimpleNamespace(
                output={
                    "type": "text",
                    "text": json.dumps(payload, ensure_ascii=False),
                }
            )
        ]
    )


def _result_with_text_list(payload: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        new_items=[
            SimpleNamespace(
                output=[
                    {"type": "text", "text": json.dumps(payload, ensure_ascii=False)}
                ]
            )
        ]
    )


def _ambiguous_payload() -> dict[str, object]:
    return {
        "result_schema_version": "okcanvas-organization-context-unified-resolve-tool-result-v1",
        "tool_name": "resolve_organization_context",
        "catalog_revision": 500,
        "resolved": False,
        "ambiguous": True,
        "candidate_count": 2,
        "returned_count": 2,
        "records": [
            {
                "entity_type": "EMPLOYEE",
                "entity_id": "employee-0017",
                "display_name": "김민수",
                "context": {
                    "department_name": "플랫폼개발팀",
                    "positions": ["선임"],
                },
            },
            {
                "entity_type": "EMPLOYEE",
                "entity_id": "employee-0034",
                "display_name": "김민수",
                "context": {
                    "department_name": "기업영업팀",
                    "positions": ["팀장", "책임"],
                },
            },
        ],
        "changes": [],
    }


def test_semantically_incomplete_ambiguous_draft_is_structurally_parseable() -> None:
    draft = OrganizationContextReadResult(
        status=OrganizationContextReadStatus.NEEDS_CLARIFICATION,
        answer="동명이인입니다.",
        queried_operations=[],
        result_count=0,
        citations=[],
        unverified=[],
    )
    assert draft.status is OrganizationContextReadStatus.NEEDS_CLARIFICATION


def test_ambiguous_tool_evidence_is_deterministically_normalized() -> None:
    draft = OrganizationContextReadResult(
        status=OrganizationContextReadStatus.NEEDS_CLARIFICATION,
        answer="추가 정보가 필요합니다.",
    )
    normalized = normalize_organization_context_nested_result(
        result=_result(_ambiguous_payload()),
        output=draft,
        request="김민수 정보",
    )
    output = normalized.output
    assert isinstance(output, OrganizationContextReadResult)
    assert output.status is OrganizationContextReadStatus.NEEDS_CLARIFICATION
    assert output.queried_operations == ["resolve_organization_context"]
    assert output.result_count == 2
    assert output.catalog_revision == 500
    assert [item.reference for item in output.citations] == ["employee-0017", "employee-0034"]
    assert all("employee-" in item for item in output.unverified)
    assert "플랫폼개발팀" in output.answer
    assert "기업영업팀" in output.answer
    assert "선임" in output.answer
    assert "팀장" in output.answer and "책임" in output.answer
    assert normalized.metadata == {
        "strategy": "deterministic-ambiguous-tool-evidence-v1",
        "tool_name": "resolve_organization_context",
        "ambiguous": True,
        "candidate_count": 2,
        "clarification_applied": True,
        "model_calls_added": 0,
        "tool_reexecuted": False,
        "model_output_persisted": False,
        "tool_result_persisted": False,
    }


def test_nonambiguous_answer_wording_is_retained_and_provenance_aligned() -> None:
    payload = {
        "tool_name": "resolve_organization_context",
        "catalog_revision": 500,
        "resolved": True,
        "ambiguous": False,
        "records": [
            {
                "entity_type": "EMPLOYEE",
                "entity_id": "employee-0017",
                "display_name": "김민수",
                "context": {"department_name": "플랫폼개발팀", "positions": ["선임"]},
            }
        ],
        "changes": [],
    }
    draft = OrganizationContextReadResult(
        status=OrganizationContextReadStatus.ANSWERED,
        answer="연락처는 user0017@tenant-a.example 입니다.",
        queried_operations=[],
        citations=[],
    )
    normalized = normalize_organization_context_nested_result(
        result=_result(payload), output=draft, request="김선임 연락처"
    )
    output = normalized.output
    assert isinstance(output, OrganizationContextReadResult)
    assert output.answer == draft.answer
    assert output.status is OrganizationContextReadStatus.ANSWERED
    assert output.queried_operations == ["resolve_organization_context"]
    assert output.result_count == 1
    assert output.catalog_revision == 500
    assert output.citations == [
        OrganizationContextReadCitation(label="김민수", reference="employee-0017")
    ]
    assert normalized.metadata["strategy"] == "tool-evidence-provenance-alignment-v1"
    assert normalized.metadata["tool_reexecuted"] is False


def test_ambiguous_evidence_without_two_stable_ids_fails_closed() -> None:
    payload = _ambiguous_payload()
    payload["records"] = [{"display_name": "김민수"}, {"display_name": "김민수"}]
    draft = OrganizationContextReadResult(
        status=OrganizationContextReadStatus.NEEDS_CLARIFICATION,
        answer="추가 정보가 필요합니다.",
    )
    with pytest.raises(ValueError, match="at least two stable IDs"):
        normalize_organization_context_nested_result(
            result=_result(payload), output=draft, request="김민수 정보"
        )



def test_sdk_mcp_text_output_list_is_decoded_without_alias_fallback() -> None:
    draft = OrganizationContextReadResult(
        status=OrganizationContextReadStatus.NEEDS_CLARIFICATION,
        answer="추가 정보가 필요합니다.",
    )
    normalized = normalize_organization_context_nested_result(
        result=_result_with_text_list(_ambiguous_payload()),
        output=draft,
        request="김민수 정보",
    )
    assert normalized.output.status is OrganizationContextReadStatus.NEEDS_CLARIFICATION
    assert [item.reference for item in normalized.output.citations] == [
        "employee-0017",
        "employee-0034",
    ]


def test_missing_allowlisted_tool_payload_reports_bounded_category() -> None:
    draft = OrganizationContextReadResult(
        status=OrganizationContextReadStatus.ANSWERED,
        answer="결과 없음",
    )
    with pytest.raises(ValueError) as captured:
        normalize_organization_context_nested_result(
            result=SimpleNamespace(
                new_items=[SimpleNamespace(output={"type": "text", "text": "not-json"})]
            ),
            output=draft,
            request="김선임 연락처",
        )
    assert getattr(captured.value, "safe_category", None) == (
        "ALLOWLISTED_MCP_TOOL_RESULT_NOT_OBSERVED"
    )

def test_output_registry_binds_product_owned_nested_normalizer() -> None:
    runtime = resolve_output_contract("OrganizationContextReadResult")
    assert runtime.supports_nested_result_normalization is True
    assert runtime.nested_result_normalizer is normalize_organization_context_nested_result
    assert runtime.nested_normalization_strategy == "product-owned-mcp-evidence-normalization-v1"
    assert runtime.runtime_version == "1.1.0"
    assert runtime.implementation_id == "organization-context-read-result-runtime-v2"
