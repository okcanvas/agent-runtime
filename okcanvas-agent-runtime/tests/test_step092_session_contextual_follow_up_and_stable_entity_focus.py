from __future__ import annotations

import base64
import json
import shutil
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.assistant_routing import OrganizationAssistantRoutingService
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.application.organization_context.result_normalization import (
    normalize_organization_context_nested_result,
)
from okcanvas_agent_runtime.adapters.persistence.postgresql import session_runtime as postgresql_session_module
from okcanvas_agent_runtime.core.contracts import OrganizationContextReadResult, OrganizationContextReadStatus
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.domain.sessions import (
    SessionContextEntityRef,
    SessionContextFocusObservation,
    SessionContextFocusRecord,
    SessionContextFocusState,
    SessionHistoryKey,
    SessionIntegrityError,
    SQLiteSessionPolicyCatalog,
    SQLiteSessionRuntimeService,
)

ROOT = Path(__file__).resolve().parents[1]
ORG_CONTEXT_ENV = "OKCANVAS_ORGANIZATION_CONTEXT_READ_BEARER"
KEY_TEXT = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
ROTATED_KEY_TEXT = base64.urlsafe_b64encode(bytes(range(32, 64))).decode("ascii")


def _configured_project(tmp_path: Path) -> Path:
    project = tmp_path / "configured-project"
    shutil.copytree(ROOT / "specs", project / "specs")
    shutil.copytree(ROOT / "reference", project / "reference")
    server_path = project / "specs/mcp/servers/organization-context-read/server.json"
    payload = json.loads(server_path.read_text(encoding="utf-8"))
    payload["url_template"] = "https://connector.example.com/tenants/{tenant_id}/mcp"
    server_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return project


def _entity(
    entity_id: str,
    *,
    label: str = "김민수",
    qualifiers: tuple[str, ...] = (),
) -> SessionContextEntityRef:
    return SessionContextEntityRef(
        entity_type="EMPLOYEE",
        entity_id=entity_id,
        label=label,
        qualifiers=qualifiers,
    )


def _focus(
    state: SessionContextFocusState,
    candidates: tuple[SessionContextEntityRef, ...],
) -> SessionContextFocusRecord:
    return SessionContextFocusRecord(
        session_id="session-step092",
        observation=SessionContextFocusObservation(
            domain="ORGANIZATION_CONTEXT",
            state=state,
            candidates=candidates,
            catalog_revision=500,
        ),
        source_run_id="run-step092-source",
        source_turn_count=1,
        updated_at="2026-08-08T00:00:00Z",
    )


def _route(router: OrganizationAssistantRoutingService, request: str, focus: SessionContextFocusRecord):
    return router.route(
        request=request,
        session_id=focus.session_id,
        tenant_id="tenant-a",
        principal_id="alice",
        roles=("agent-user",),
        session_context_focus=focus,
    )


def test_step092_runtime_contract_declares_product_owned_context_focus() -> None:
    info = RuntimeInfo()
    policy = json.loads(
        (ROOT / "specs/assistant/session-context-follow-up-policy.json").read_text(encoding="utf-8")
    )
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.organization_context_session_focus_implemented is True
    assert info.organization_context_session_focus_source == "NORMALIZED_MCP_TOOL_EVIDENCE"
    assert info.organization_context_session_focus_raw_tool_result_persisted is False
    assert info.organization_context_session_focus_recency == "LAST_COMMITTED_TURN_ONLY"
    assert info.organization_context_session_follow_up_get_by_stable_id is True
    assert info.organization_context_session_follow_up_ambiguous_guessing_enabled is False
    assert info.organization_context_session_follow_up_deterministic_accepted is False
    assert info.organization_context_session_follow_up_windows_live_accepted is False
    assert policy["policy_id"] == "session-contextual-follow-up-stable-entity-v1"
    assert policy["version"] == "1.0.0"
    assert policy["max_candidates"] == 20


def test_step092_resolved_focus_supports_deictic_and_ellipsis_follow_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(ORG_CONTEXT_ENV, "connector-secret")
    router = OrganizationAssistantRoutingService(str(project))
    focus = _focus(
        SessionContextFocusState.RESOLVED,
        (_entity("employee-0017", qualifiers=("플랫폼개발팀", "선임")),),
    )
    cases = {
        "그 사람 연락처는?": ("CONTACT", "employee-0017"),
        "그 사람의 이메일은?": ("CONTACT", "employee-0017"),
        "전화번호는?": ("CONTACT", "employee-0017"),
        "그럼 직책은?": ("POSITION", "employee-0017"),
        "그럼, 직책은?": ("POSITION", "employee-0017"),
        "그분": ("DETAIL", "employee-0017"),
    }
    for request, (field, entity_id) in cases.items():
        decision = _route(router, request, focus)
        assert decision.status.value == "EXECUTABLE"
        assert decision.selected_agent_id == "organization-context-session-agent"
        assert decision.organization_context_request_hint is not None
        hint = decision.organization_context_request_hint
        assert hint.preferred_operation.value == "GET"
        assert hint.target_expression == entity_id
        assert list(hint.requested_fields) == [field]
        assert "stable-entity-id-bound-in-immutable-read-routing-hint" in decision.reasons
        model_request = router.build_model_request(decision, request)
        assert entity_id in model_request
        assert "connector-secret" not in model_request


def test_step092_ambiguous_focus_never_guesses_and_allows_bounded_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(ORG_CONTEXT_ENV, "connector-secret")
    router = OrganizationAssistantRoutingService(str(project))
    focus = _focus(
        SessionContextFocusState.AMBIGUOUS,
        (
            _entity("employee-0017", qualifiers=("플랫폼개발팀", "선임")),
            _entity("employee-0034", qualifiers=("기업영업팀", "팀장", "책임")),
        ),
    )

    vague = _route(router, "그 사람 연락처는?", focus)
    assert vague.status.value == "AMBIGUOUS"
    assert vague.selected_agent_id is None
    assert vague.organization_context_request_hint is None
    assert "model-guessing-blocked" in vague.reasons

    same_name = _route(router, "김민수 연락처는?", focus)
    assert same_name.status.value == "AMBIGUOUS"
    assert same_name.selected_agent_id is None

    ordinal = _route(router, "두 번째 사람 연락처는?", focus)
    assert ordinal.status.value == "EXECUTABLE"
    assert ordinal.organization_context_request_hint is not None
    assert ordinal.organization_context_request_hint.target_expression == "employee-0034"
    assert ordinal.organization_context_request_hint.preferred_operation.value == "GET"

    refined = _route(router, "플랫폼개발팀 김민수 연락처는?", focus)
    assert refined.status.value == "EXECUTABLE"
    assert refined.organization_context_request_hint is not None
    assert refined.organization_context_request_hint.target_expression == "employee-0017"
    assert refined.organization_context_request_hint.preferred_operation.value == "GET"




def test_step092_get_result_must_match_immutable_stable_entity_focus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(ORG_CONTEXT_ENV, "connector-secret")
    router = OrganizationAssistantRoutingService(str(project))
    focus = _focus(
        SessionContextFocusState.RESOLVED,
        (_entity("employee-0017", qualifiers=("플랫폼개발팀", "선임")),),
    )
    decision = _route(router, "그 사람 연락처는?", focus)
    request = router.build_model_request(decision, "그 사람 연락처는?")
    wrong_payload = {
        "result_schema_version": "okcanvas-organization-context-get-entity-tool-result-v1",
        "tool_name": "get_organization_entity",
        "catalog_revision": 501,
        "records": [
            {
                "entity_type": "EMPLOYEE",
                "entity_id": "employee-0034",
                "display_name": "김민수",
                "context": {"department_name": "기업영업팀", "positions": ["팀장"]},
            }
        ],
        "changes": [],
    }
    result = SimpleNamespace(
        new_items=[
            SimpleNamespace(
                output={"type": "text", "text": json.dumps(wrong_payload, ensure_ascii=False)}
            )
        ]
    )
    draft = OrganizationContextReadResult(
        status=OrganizationContextReadStatus.ANSWERED,
        answer="모델이 잘못된 대상을 선택했습니다.",
    )
    with pytest.raises(ValueError, match="does not match the immutable Session focus"):
        normalize_organization_context_nested_result(result=result, output=draft, request=request)

    empty_payload = {
        **wrong_payload,
        "records": [],
    }
    empty_result = SimpleNamespace(
        new_items=[
            SimpleNamespace(
                output={"type": "text", "text": json.dumps(empty_payload, ensure_ascii=False)}
            )
        ]
    )
    with pytest.raises(ValueError, match="must return exactly one entity"):
        normalize_organization_context_nested_result(result=empty_result, output=draft, request=request)


def test_step092_context_focus_is_persisted_atomically_with_committed_turn(tmp_path: Path) -> None:
    policy = SQLiteSessionPolicyCatalog(ROOT).resolve()
    runtime = SQLiteSessionRuntimeService(
        tmp_path / "sessions", policy, SessionHistoryKey.from_text(KEY_TEXT)
    )
    runtime.initialize()
    definition = AgentDefinitionCatalog(ROOT).resolve("session-continuity-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    session = runtime.create(
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    runtime.acquire_turn(
        session_id=session.session_id,
        run_id="run-step092-commit",
        definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    observation = _focus(
        SessionContextFocusState.RESOLVED,
        (_entity("employee-0017", qualifiers=("플랫폼개발팀", "선임")),),
    ).observation
    runtime.release_turn(
        session_id=session.session_id,
        run_id="run-step092-commit",
        succeeded=True,
        item_count=2,
        context_focus=observation,
    )
    loaded = runtime.get_context_focus(session.session_id)
    assert loaded is not None
    assert loaded.source_run_id == "run-step092-commit"
    assert loaded.source_turn_count == 1
    assert loaded.active_entity is not None
    assert loaded.active_entity.entity_id == "employee-0017"
    assert loaded.catalog_revision == 500


def test_step092_failed_turn_does_not_replace_previous_focus(tmp_path: Path) -> None:
    policy = SQLiteSessionPolicyCatalog(ROOT).resolve()
    runtime = SQLiteSessionRuntimeService(
        tmp_path / "sessions", policy, SessionHistoryKey.from_text(KEY_TEXT)
    )
    runtime.initialize()
    definition = AgentDefinitionCatalog(ROOT).resolve("session-continuity-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    session = runtime.create(definition=definition, runtime_binding_sha256=binding.runtime_binding_sha256)
    first = _focus(SessionContextFocusState.RESOLVED, (_entity("employee-0017"),)).observation
    second = _focus(SessionContextFocusState.RESOLVED, (_entity("employee-0034"),)).observation
    runtime.acquire_turn(
        session_id=session.session_id, run_id="run-step092-a", definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    runtime.release_turn(
        session_id=session.session_id, run_id="run-step092-a", succeeded=True,
        item_count=2, context_focus=first,
    )
    runtime.acquire_turn(
        session_id=session.session_id, run_id="run-step092-b", definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    runtime.release_turn(
        session_id=session.session_id, run_id="run-step092-b", succeeded=False,
        item_count=2, context_focus=second,
    )
    loaded = runtime.get_context_focus(session.session_id)
    assert loaded is not None and loaded.active_entity is not None
    assert loaded.active_entity.entity_id == "employee-0017"


def test_step092_focus_is_valid_only_for_the_most_recent_committed_turn(tmp_path: Path) -> None:
    policy = SQLiteSessionPolicyCatalog(ROOT).resolve()
    runtime = SQLiteSessionRuntimeService(
        tmp_path / "sessions", policy, SessionHistoryKey.from_text(KEY_TEXT)
    )
    runtime.initialize()
    definition = AgentDefinitionCatalog(ROOT).resolve("session-continuity-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    session = runtime.create(definition=definition, runtime_binding_sha256=binding.runtime_binding_sha256)
    observation = _focus(SessionContextFocusState.RESOLVED, (_entity("employee-0017"),)).observation
    runtime.acquire_turn(
        session_id=session.session_id, run_id="run-step092-focus", definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    runtime.release_turn(
        session_id=session.session_id, run_id="run-step092-focus", succeeded=True,
        item_count=1, context_focus=observation,
    )
    assert runtime.get_context_focus(session.session_id) is not None
    runtime.acquire_turn(
        session_id=session.session_id, run_id="run-step092-unrelated", definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    runtime.release_turn(
        session_id=session.session_id, run_id="run-step092-unrelated", succeeded=True,
        item_count=2, context_focus=None,
    )
    assert runtime.get_context_focus(session.session_id) is None


def test_step092_focus_integrity_and_history_key_binding_fail_closed(tmp_path: Path) -> None:
    policy = SQLiteSessionPolicyCatalog(ROOT).resolve()
    runtime = SQLiteSessionRuntimeService(
        tmp_path / "sessions", policy, SessionHistoryKey.from_text(KEY_TEXT)
    )
    runtime.initialize()
    definition = AgentDefinitionCatalog(ROOT).resolve("session-continuity-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    session = runtime.create(definition=definition, runtime_binding_sha256=binding.runtime_binding_sha256)
    observation = _focus(SessionContextFocusState.RESOLVED, (_entity("employee-0017"),)).observation
    runtime.acquire_turn(
        session_id=session.session_id, run_id="run-step092", definition=definition,
        runtime_binding_sha256=binding.runtime_binding_sha256,
    )
    runtime.release_turn(
        session_id=session.session_id, run_id="run-step092", succeeded=True,
        item_count=1, context_focus=observation,
    )
    with sqlite3.connect(runtime.catalog_db) as conn:
        conn.execute(
            "UPDATE product_session_context_focus SET context_json=? WHERE session_id=?",
            ('{"tampered":true}', session.session_id),
        )
    with pytest.raises(SessionIntegrityError, match="payload is invalid"):
        runtime.get_context_focus(session.session_id)

    with sqlite3.connect(runtime.catalog_db) as conn:
        payload = observation.canonical_json()
        conn.execute(
            "UPDATE product_session_context_focus SET context_json=?, context_sha256=? WHERE session_id=?",
            (payload, observation.sha256, session.session_id),
        )
    runtime.history_key = SessionHistoryKey.from_text(ROTATED_KEY_TEXT)
    with pytest.raises(SessionIntegrityError, match="key ID changed"):
        runtime.get_context_focus(session.session_id)


def test_step092_postgresql_session_schema_adds_focus_without_rewriting_historical_evidence() -> None:
    schema = postgresql_session_module._SCHEMA
    assert "CREATE TABLE IF NOT EXISTS product_session_context_focus" in schema
    assert "context_sha256 TEXT NOT NULL" in schema
    assert "source_run_id TEXT NOT NULL" in schema
    assert "source_turn_count INTEGER NOT NULL" in schema
    historical = ROOT / "scripts/run_step091b3r1_postgresql_live_acceptance.py"
    text = historical.read_text(encoding="utf-8")
    assert 'STEP = "STEP091B3R1_REAL_POSTGRESQL_LIVE_ACCEPTANCE_GATE"' in text
    assert 'VERSION = "2.74.1"' in text
    assert '"product_session_context_focus"' not in text


def test_step092_ambiguous_public_candidates_match_persisted_focus_bound() -> None:
    records = [
        {
            "entity_type": "EMPLOYEE",
            "entity_id": f"employee-{index:04d}",
            "display_name": f"후보 {index}",
            "context": {"department_name": f"부서 {index}", "positions": ["구성원"]},
        }
        for index in range(1, 26)
    ]
    payload = {
        "result_schema_version": "okcanvas-organization-context-resolve-tool-result-v1",
        "tool_name": "resolve_organization_context",
        "catalog_revision": 600,
        "ambiguous": True,
        "records": records,
        "changes": [],
    }
    result = SimpleNamespace(
        new_items=[
            SimpleNamespace(
                output={"type": "text", "text": json.dumps(payload, ensure_ascii=False)}
            )
        ]
    )
    draft = OrganizationContextReadResult(
        status=OrganizationContextReadStatus.NEEDS_CLARIFICATION,
        answer="후보를 확인해 주세요.",
    )
    normalized = normalize_organization_context_nested_result(
        result=result,
        output=draft,
        request="김민수 정보",
    )
    focus_payload = normalized.metadata["session_context_focus"]
    assert isinstance(focus_payload, dict)
    assert normalized.output.result_count == 20
    assert len(normalized.output.citations) == 20
    assert len(focus_payload["candidates"]) == 20
    assert normalized.output.citations[0].reference == focus_payload["candidates"][0]["entity_id"]
    assert normalized.output.citations[-1].reference == focus_payload["candidates"][-1]["entity_id"]
