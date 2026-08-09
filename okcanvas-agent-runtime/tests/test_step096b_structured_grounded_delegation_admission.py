from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.agent.subagents.agent_tools.runtime import build_sdk_agent_tool
from dataclasses import replace

from okcanvas_agent_runtime.application.assistant_interpretation import (
    GroundedDelegationAdmission,
    GroundedDelegationContractError,
    GroupwareReadDelegationInput,
    OrganizationReadDelegationInput,
    extract_grounded_routing_context,
    grounded_structured_delegation_requested,
)
from okcanvas_agent_runtime.application.assistant_routing.service import OrganizationAssistantRoutingService
from okcanvas_agent_runtime.application.groupware_read import (
    GroupwareReadState,
    groupware_context_filter,
    groupware_named_tool_choice,
    groupware_operation_hint,
)
from okcanvas_agent_runtime.application.groupware_read.result_normalization import (
    GroupwareNormalizationError,
    normalize_groupware_nested_result,
)
from okcanvas_agent_runtime.application.mcp_access import DelegatedMCPIdentity
from okcanvas_agent_runtime.core.contracts import GroupwareReadResult, GroupwareReadStatus
from okcanvas_agent_runtime.application.organization_context import (
    OrganizationContextReadState,
    organization_context_named_tool_choice,
    organization_context_request_hint,
)
from okcanvas_agent_runtime.domain.sessions.context_focus import (
    SessionContextEntityRef,
    SessionContextFocusObservation,
    SessionContextFocusRecord,
    SessionContextFocusState,
)

ROOT = Path(__file__).resolve().parents[1]


def _identity() -> DelegatedMCPIdentity:
    return DelegatedMCPIdentity.create(
        tenant_id="tenant-a", principal_id="alice", roles=("agent-user",)
    )


def _focus(entity_type: str = "EMPLOYEE") -> SessionContextFocusRecord:
    entity = SessionContextEntityRef(
        entity_type=entity_type,
        entity_id="employee-0017" if entity_type == "EMPLOYEE" else "client-0001",
        label="김민수" if entity_type == "EMPLOYEE" else "한빛산업",
        qualifiers=("플랫폼개발팀",) if entity_type == "EMPLOYEE" else ("영업본부",),
    )
    return SessionContextFocusRecord(
        session_id="session-step096b",
        observation=SessionContextFocusObservation(
            domain="ORGANIZATION_CONTEXT",
            state=SessionContextFocusState.RESOLVED,
            candidates=(entity,),
            catalog_revision=777,
        ),
        source_run_id="run-step096b-source",
        source_turn_count=1,
        updated_at="2026-08-09T00:00:00Z",
    )


def _admission(monkeypatch: pytest.MonkeyPatch) -> GroundedDelegationAdmission:
    admission = GroundedDelegationAdmission(str(ROOT))
    monkeypatch.setattr(
        admission._organization,
        "readiness",
        lambda identity: SimpleNamespace(state=OrganizationContextReadState.READY),
    )
    monkeypatch.setattr(
        admission._groupware,
        "readiness",
        lambda identity: SimpleNamespace(state=GroupwareReadState.READY),
    )
    return admission


def test_step096b_structured_inputs_have_no_stable_id_or_tool_name_surface() -> None:
    with pytest.raises(ValidationError):
        OrganizationReadDelegationInput.model_validate(
            {
                "intent_kind": "ENTITY_FIELD_LOOKUP",
                "preferred_operation": "GET",
                "requested_fields": ["CONTACT"],
                "context_reference_mode": "SESSION_FOCUS",
                "entity_id": "employee-0017",
            }
        )
    with pytest.raises(ValidationError):
        GroupwareReadDelegationInput.model_validate(
            {
                "resource_kind": "CALENDAR",
                "context_reference_mode": "SESSION_FOCUS",
                "tool_name": "list_calendar_events",
            }
        )


def test_step096b_organization_session_focus_get_injects_runtime_stable_id(monkeypatch: pytest.MonkeyPatch) -> None:
    admission = _admission(monkeypatch)
    request = admission.admit_organization(
        raw={
            "intent_kind": "ENTITY_FIELD_LOOKUP",
            "preferred_operation": "GET",
            "target_expression": None,
            "entity_type_hints": [],
            "requested_fields": ["CONTACT"],
            "context_reference_mode": "SESSION_FOCUS",
        },
        user_utterance="그 사람 연락처 알려줘",
        delegated_identity=_identity(),
        session_focus=_focus(),
    )
    hint = organization_context_request_hint(request)
    assert hint["target_expression"] == "employee-0017"
    assert hint["entity_type_hints"] == ["EMPLOYEE"]
    assert hint["requested_fields"] == ["CONTACT"]
    assert organization_context_named_tool_choice(request) == "get_organization_entity"
    assert request.endswith("USER REQUEST:\n그 사람 연락처 알려줘")


def test_step096b_model_cannot_supply_get_identity_without_runtime_focus(monkeypatch: pytest.MonkeyPatch) -> None:
    admission = _admission(monkeypatch)
    with pytest.raises(GroundedDelegationContractError, match="GET cannot accept"):
        admission.admit_organization(
            raw={
                "intent_kind": "ENTITY_DETAIL_LOOKUP",
                "preferred_operation": "GET",
                "target_expression": "employee-0017",
                "requested_fields": ["DETAIL"],
                "context_reference_mode": "NONE",
            },
            user_utterance="김민수 정보",
            delegated_identity=_identity(),
            session_focus=None,
        )


def test_step096b_organization_resolve_preserves_model_surface_not_stable_id(monkeypatch: pytest.MonkeyPatch) -> None:
    admission = _admission(monkeypatch)
    request = admission.admit_organization(
        raw={
            "intent_kind": "ENTITY_FIELD_LOOKUP",
            "preferred_operation": "RESOLVE",
            "target_expression": "김민수",
            "entity_type_hints": ["EMPLOYEE"],
            "requested_fields": ["CONTACT"],
            "context_reference_mode": "NONE",
        },
        user_utterance="김민수 연락처 좀 알려줘",
        delegated_identity=_identity(),
        session_focus=None,
    )
    hint = organization_context_request_hint(request)
    assert hint["target_expression"] == "김민수"
    assert hint["entity_type_hints"] == ["EMPLOYEE"]
    assert organization_context_named_tool_choice(request) == "resolve_organization_context"
    assert "employee-0017" not in request


def test_step096b_groupware_session_focus_builds_exact_context_filter_and_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    admission = _admission(monkeypatch)
    request = admission.admit_groupware(
        raw={
            "resource_kind": "CALENDAR",
            "context_reference_mode": "SESSION_FOCUS",
        },
        user_utterance="그 사람 일정 알려줘",
        delegated_identity=_identity(),
        session_focus=_focus(),
    )
    operation = groupware_operation_hint(request)
    hint = groupware_context_filter(request)
    assert operation["tool_name"] == "list_calendar_events"
    assert groupware_named_tool_choice(request) == "list_calendar_events"
    assert hint["entity_type"] == "EMPLOYEE"
    assert hint["entity_id"] == "employee-0017"
    assert hint["catalog_revision"] == 777
    assert hint["max_results"] == 20


def test_step096b_groupware_without_focus_has_operation_but_no_context_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    admission = _admission(monkeypatch)
    request = admission.admit_groupware(
        raw={"resource_kind": "MAIL", "context_reference_mode": "NONE"},
        user_utterance="오늘 메일 보여줘",
        delegated_identity=_identity(),
        session_focus=None,
    )
    assert groupware_named_tool_choice(request) == "search_mail"
    assert groupware_context_filter(request) == {}
    assert groupware_operation_hint(request)["resource_kind"] == "MAIL"


def test_step096b_agent_as_tool_builder_forwards_structured_schema_and_admission_builder() -> None:
    child = AgentDefinitionCatalog(ROOT).resolve("organization-context-read-agent")
    captured: dict[str, object] = {}

    class FakeAgent:
        def as_tool(self, **kwargs):
            captured.update(kwargs)
            return "sdk-tool"

    async def input_builder(options):
        return "admitted"

    policy = SimpleNamespace(
        inherit_parent_run_config=False,
        nested_stream_enabled=True,
    )
    result = build_sdk_agent_tool(
        child_sdk_agent=FakeAgent(),
        child_definition=child,
        policy=policy,
        run_config=object(),
        hooks=object(),
        on_stream=lambda event: None,
        custom_output_extractor=lambda result: None,
        parameters=OrganizationReadDelegationInput,
        input_builder=input_builder,
        tool_description="grounded organization read",
    )
    assert result == "sdk-tool"
    assert captured["parameters"] is OrganizationReadDelegationInput
    assert captured["input_builder"] is input_builder
    assert captured["tool_description"] == "grounded organization read"
    assert captured["needs_approval"] is False


def test_step096b_gateway_declares_requested_admitted_started_and_lazy_mcp_contract() -> None:
    source = (ROOT / "okcanvas_agent_runtime/adapters/openai/generic_gateway.py").read_text(encoding="utf-8")
    for token in (
        '"agent.tool.requested"',
        '"agent.tool.admitted"',
        '"agent.tool.admission.denied"',
        "await server.connect()",
        "await server.cleanup()",
        "parameters=parameters",
        "input_builder=grounded_input_builder",
        "grounded_structured_delegation_enabled",
        "grounded_agent_tool_request_count",
    ):
        assert token in source
    assert "stable_ids_from_model_accepted" in source


def test_step096b_root_definition_still_has_no_direct_mcp_and_exactly_two_read_children() -> None:
    root = AgentDefinitionCatalog(ROOT).resolve("organization-assistant-session-agent")
    assert root.mcp_servers == ()
    assert root.agent_tools == ("groupware-read-agent", "organization-context-read-agent")


def test_step096b_build_model_request_marks_grounded_structured_delegation_explicitly() -> None:
    router = OrganizationAssistantRoutingService(str(ROOT))
    decision = router.route(
        request="안녕하세요",
        session_id="session-step096b",
        tenant_id="tenant-a",
        principal_id="alice",
        roles=("agent-user",),
    )
    legacy_request = router.build_model_request(decision, "안녕하세요")
    assert grounded_structured_delegation_requested(extract_grounded_routing_context(legacy_request)) is False

    grounded = replace(
        decision,
        grounded_interpretation_shadow=router.grounded_session_route_shadow(),
    )
    grounded_request = router.build_model_request(grounded, "안녕하세요")
    context = extract_grounded_routing_context(grounded_request)
    assert grounded_structured_delegation_requested(context) is True
    assert context is not None
    marker = context["grounded_structured_delegation"]
    assert marker["max_child_calls"] == 1
    assert marker["max_child_requests"] == 1
    assert marker["stable_ids_from_model_accepted"] is False
    assert marker["write_enabled"] is False
    assert marker["legacy_child_selection_authoritative"] is False


def test_step096b_policy_and_root_instructions_preserve_llm_interpretation_runtime_authority() -> None:
    policy = json.loads(
        (ROOT / "specs/assistant/grounded-structured-delegation-policy.json").read_text(encoding="utf-8")
    )
    assert policy["allowed_capabilities"] == ["groupware-read-v1", "organization-context-read-v1"]
    assert policy["max_child_calls_per_turn"] == 1
    assert policy["max_child_requests_per_turn"] == 1
    assert policy["stable_ids_from_model_accepted"] is False
    assert policy["runtime_admission_required"] is True
    assert policy["child_mcp_connection"] == "LAZY_AFTER_ADMISSION"
    assert policy["root_direct_mcp_enabled"] is False
    instructions = (
        ROOT / "specs/agents/organization-assistant-session-agent/instructions.md"
    ).read_text(encoding="utf-8")
    for phrase in (
        "`required_capabilities` value is not child-selection authority",
        "request exactly one read-only specialist",
        "Never request both specialists in one Turn",
        "never reinterpret it as a read",
        "admission, not your Tool selection",
    ):
        assert phrase in instructions


def _groupware_tool_result(tool_name: str):
    payload = {
        "result_schema_version": "okcanvas-groupware-read-tool-result-v2",
        "tool_name": tool_name,
        "context_ref": None,
        "records": [],
    }
    return SimpleNamespace(
        new_items=[SimpleNamespace(output={"type": "text", "text": json.dumps(payload, ensure_ascii=False)})]
    )


def test_step096b_groupware_operation_admission_requires_exact_observed_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    admission = _admission(monkeypatch)
    request = admission.admit_groupware(
        raw={"resource_kind": "MAIL", "context_reference_mode": "NONE"},
        user_utterance="오늘 메일 보여줘",
        delegated_identity=_identity(),
        session_focus=None,
    )
    draft = GroupwareReadResult(
        status=GroupwareReadStatus.ANSWERED,
        answer="메일입니다.",
        queried_operations=["search_mail"],
    )
    normalized = normalize_groupware_nested_result(
        result=_groupware_tool_result("search_mail"), output=draft, request=request
    )
    assert normalized.metadata["strategy"] == "grounded-groupware-operation-admission-v1"
    assert normalized.metadata["tool_name"] == "search_mail"

    with pytest.raises(GroupwareNormalizationError) as exc:
        normalize_groupware_nested_result(
            result=_groupware_tool_result("search_notices"), output=draft, request=request
        )
    assert exc.value.safe_category == "GROUPWARE_OPERATION_TOOL_MISMATCH"


@pytest.mark.parametrize("side_effect", ["DRAFT", "WRITE_IRREVERSIBLE", "AUTOMATION_DEFINITION"])
def test_step096b_product_owned_non_read_side_effect_cannot_be_overridden_by_read_child(
    monkeypatch: pytest.MonkeyPatch, side_effect: str
) -> None:
    admission = _admission(monkeypatch)
    with pytest.raises(GroundedDelegationContractError, match="non-read side-effect"):
        admission.admit_groupware(
            raw={"resource_kind": "MAIL", "context_reference_mode": "NONE"},
            user_utterance="처리해줘",
            delegated_identity=_identity(),
            session_focus=None,
            parent_side_effect=side_effect,
        )
