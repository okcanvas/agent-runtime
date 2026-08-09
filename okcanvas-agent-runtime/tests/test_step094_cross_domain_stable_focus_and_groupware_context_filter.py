from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from okcanvas_agent_protocols.rest.admin import AssistantRouteResponse
from okcanvas_agent_runtime.application.assistant_routing import OrganizationAssistantRoutingService
from okcanvas_agent_runtime.application.groupware_read import groupware_named_tool_choice
from okcanvas_agent_runtime.application.groupware_read.result_normalization import (
    GroupwareNormalizationError,
    normalize_groupware_nested_result,
)
from okcanvas_agent_runtime.core.contracts import GroupwareReadResult, GroupwareReadStatus
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.domain.sessions import (
    SessionContextEntityRef,
    SessionContextFocusObservation,
    SessionContextFocusRecord,
    SessionContextFocusState,
)

ROOT = Path(__file__).resolve().parents[1]
GROUPWARE_ENV = "OKCANVAS_GROUPWARE_READ_BEARER"


def _configured_project(tmp_path: Path) -> Path:
    project = tmp_path / "configured-project"
    shutil.copytree(ROOT / "specs", project / "specs")
    shutil.copytree(ROOT / "reference", project / "reference")
    server_path = project / "specs/mcp/servers/groupware-read/server.json"
    payload = json.loads(server_path.read_text(encoding="utf-8"))
    payload["url_template"] = "https://groupware.example.com/tenants/{tenant_id}/mcp"
    server_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return project


def _ref(entity_type: str, entity_id: str, label: str, *qualifiers: str) -> SessionContextEntityRef:
    return SessionContextEntityRef(
        entity_type=entity_type,
        entity_id=entity_id,
        label=label,
        qualifiers=tuple(qualifiers),
    )


def _focus(state: SessionContextFocusState, candidates: tuple[SessionContextEntityRef, ...]) -> SessionContextFocusRecord:
    return SessionContextFocusRecord(
        session_id="session-step094",
        observation=SessionContextFocusObservation(
            domain="ORGANIZATION_CONTEXT",
            state=state,
            candidates=candidates,
            catalog_revision=700,
        ),
        source_run_id="run-step094-source",
        source_turn_count=1,
        updated_at="2026-08-08T00:00:00Z",
    )


def _route(router: OrganizationAssistantRoutingService, request: str, focus: SessionContextFocusRecord):
    return router.route(
        request=request,
        session_id=focus.session_id,
        tenant_id="tenant-a",
        principal_id="user-001",
        roles=("agent-user",),
        session_context_focus=focus,
    )


def _tool_result(*, tool_name: str, context_ref: dict[str, str] | None, records: list[dict[str, object]]):
    payload = {
        "result_schema_version": "okcanvas-groupware-read-tool-result-v2",
        "tool_name": tool_name,
        "context_ref": context_ref,
        "records": records,
    }
    return SimpleNamespace(
        new_items=[
            SimpleNamespace(
                output={"type": "text", "text": json.dumps(payload, ensure_ascii=False)}
            )
        ]
    )


def test_step094_runtime_contract_declares_cross_domain_stable_focus() -> None:
    info = RuntimeInfo()
    policy = json.loads(
        (ROOT / "specs/assistant/session-cross-domain-groupware-policy.json").read_text(encoding="utf-8")
    )
    assert info.step == "STEP094_CROSS_DOMAIN_STABLE_FOCUS_AND_GROUPWARE_CONTEXT_FILTER"
    assert info.version == "2.78.0"
    assert info.cross_domain_groupware_stable_focus_implemented is True
    assert info.cross_domain_groupware_stable_focus_source == "ORGANIZATION_CONTEXT_NORMALIZED_STABLE_ID"
    assert info.cross_domain_groupware_context_filter_exact is True
    assert info.cross_domain_groupware_context_filter_authorization_additive_only is True
    assert info.cross_domain_groupware_tool_evidence_revalidated is True
    assert info.cross_domain_groupware_label_fallback_allowed is False
    assert info.cross_domain_groupware_deterministic_accepted is False
    assert info.cross_domain_groupware_windows_live_accepted is False
    assert policy["policy_id"] == "session-cross-domain-groupware-v1"
    assert policy["multiple_focus_must_not_guess"] is True


def test_step094_resolved_employee_focus_routes_exact_calendar_context_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(GROUPWARE_ENV, "connector-secret")
    router = OrganizationAssistantRoutingService(str(project))
    focus = _focus(
        SessionContextFocusState.RESOLVED,
        (_ref("EMPLOYEE", "employee-0017", "김민수", "플랫폼개발팀", "선임"),),
    )
    decision = _route(router, "그 사람 일정은?", focus)
    assert decision.status.value == "EXECUTABLE"
    assert decision.selected_agent_id == "organization-assistant-session-agent"
    assert decision.organization_context_request_hint is None
    hint = decision.groupware_context_filter
    assert hint is not None
    assert hint.tool_name == "list_calendar_events"
    assert hint.resource_kind == "CALENDAR"
    assert hint.entity_type == "EMPLOYEE"
    assert hint.entity_id == "employee-0017"
    request = router.build_model_request(decision, "그 사람 일정은?")
    assert groupware_named_tool_choice(request) == "list_calendar_events"
    assert '"entity_id": "employee-0017"' in request
    assert "connector-secret" not in request


def test_step094_multi_candidate_focus_never_guesses_cross_domain_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(GROUPWARE_ENV, "connector-secret")
    router = OrganizationAssistantRoutingService(str(project))
    focus = _focus(
        SessionContextFocusState.AMBIGUOUS,
        (
            _ref("EMPLOYEE", "employee-0017", "김민수", "플랫폼개발팀"),
            _ref("EMPLOYEE", "employee-0034", "김민수", "영업팀"),
        ),
    )
    decision = _route(router, "그 사람 일정은?", focus)
    assert decision.status.value == "AMBIGUOUS"
    assert decision.selected_agent_id is None
    assert decision.groupware_context_filter is None
    assert "cross-domain-focus-must-not-guess" in decision.reasons


def test_step094_exact_groupware_tool_evidence_preserves_prior_organization_focus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(GROUPWARE_ENV, "connector-secret")
    router = OrganizationAssistantRoutingService(str(project))
    focus = _focus(
        SessionContextFocusState.RESOLVED,
        (_ref("EMPLOYEE", "employee-0017", "김민수", "플랫폼개발팀", "선임"),),
    )
    decision = _route(router, "그 사람 일정은?", focus)
    request = router.build_model_request(decision, "그 사람 일정은?")
    context_ref = {"entity_type": "EMPLOYEE", "entity_id": "employee-0017"}
    records = [
        {
            "record_id": "event-001",
            "title": "플랫폼 프로젝트 주간 회의",
            "context_refs": [context_ref],
        }
    ]
    normalized = normalize_groupware_nested_result(
        result=_tool_result(tool_name="list_calendar_events", context_ref=context_ref, records=records),
        output=GroupwareReadResult(status=GroupwareReadStatus.ANSWERED, answer="주간 회의가 있습니다.", queried_operations=["list_calendar_events"]),
        request=request,
    )
    assert normalized.output.queried_operations == ["list_calendar_events"]
    assert normalized.output.result_count == 1
    assert normalized.output.citations[0].reference == "event-001"
    assert normalized.metadata["context_filter_applied"] is True
    focus_payload = normalized.metadata["session_context_focus"]
    assert focus_payload["state"] == "RESOLVED"
    assert focus_payload["candidates"][0]["entity_id"] == "employee-0017"


def test_step094_groupware_filter_evidence_mismatch_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(GROUPWARE_ENV, "connector-secret")
    router = OrganizationAssistantRoutingService(str(project))
    focus = _focus(SessionContextFocusState.RESOLVED, (_ref("EMPLOYEE", "employee-0017", "김민수"),))
    decision = _route(router, "그 사람 관련 공지 알려줘", focus)
    request = router.build_model_request(decision, "그 사람 관련 공지 알려줘")
    expected = {"entity_type": "EMPLOYEE", "entity_id": "employee-0017"}
    wrong = {"entity_type": "EMPLOYEE", "entity_id": "employee-0034"}
    draft = GroupwareReadResult(status=GroupwareReadStatus.ANSWERED, answer="공지입니다.", queried_operations=["search_notices"])

    with pytest.raises(GroupwareNormalizationError, match="did not apply"):
        normalize_groupware_nested_result(
            result=_tool_result(tool_name="search_notices", context_ref=wrong, records=[]),
            output=draft,
            request=request,
        )

    with pytest.raises(GroupwareNormalizationError, match="does not carry"):
        normalize_groupware_nested_result(
            result=_tool_result(
                tool_name="search_notices",
                context_ref=expected,
                records=[{"record_id": "notice-001", "title": "공지", "context_refs": [wrong]}],
            ),
            output=draft,
            request=request,
        )


def test_step094_plain_groupware_request_does_not_invent_context_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(GROUPWARE_ENV, "connector-secret")
    router = OrganizationAssistantRoutingService(str(project))
    decision = router.route(
        request="이번 주 내 일정을 보여줘",
        tenant_id="tenant-a",
        principal_id="user-001",
        roles=("agent-user",),
    )
    assert decision.status.value == "EXECUTABLE"
    assert decision.groupware_context_filter is None
    request = router.build_model_request(decision, "이번 주 내 일정을 보여줘")
    assert groupware_named_tool_choice(request) is None


def test_step094_rest_route_protocol_accepts_typed_groupware_context_filter() -> None:
    response = AssistantRouteResponse(
        request_class="READ_SYSTEM",
        side_effect="READ",
        status="EXECUTABLE",
        selected_agent_definition_id="organization-assistant-session-agent",
        executable_now=True,
        required_capabilities=[],
        matched_rule_id="groupware-read-session-stateless-subagent-v1",
        reasons=["cross-domain-groupware-reference-detected"],
        policy_id="assistant-routing-v1",
        policy_version="1.0.0",
        policy_sha256="0" * 64,
        grounding_state="NOT_APPLICABLE",
        grounding_catalog_id=None,
        grounding_catalog_version=None,
        grounding_effective_at=None,
        grounding=[],
        groupware_context_filter={
            "pattern_id": "session-cross-domain-groupware-context-ref-v1",
            "resource_kind": "CALENDAR",
            "tool_name": "list_calendar_events",
            "entity_type": "EMPLOYEE",
            "entity_id": "employee-0017",
            "label": "김민수",
            "qualifiers": ["플랫폼개발팀", "선임"],
            "catalog_revision": 700,
            "max_results": 20,
        },
    )
    assert response.groupware_context_filter is not None
    assert response.groupware_context_filter.entity_id == "employee-0017"
    assert response.groupware_context_filter.tool_name == "list_calendar_events"


def test_step094_groupware_provider_contract_is_v3_with_stable_context_ref() -> None:
    provider = json.loads((ROOT / "specs/groupware/read-provider-contract.json").read_text(encoding="utf-8"))
    assert provider["schema_version"] == "okcanvas-groupware-read-provider-contract-v3"
    fixtures = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((ROOT / "fixtures/groupware/read-provider-contract").glob("*.json"))
    ]
    assert len(fixtures) == 3
    assert all("context_ref" in payload for payload in fixtures)
