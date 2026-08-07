from __future__ import annotations

from pathlib import Path

from okcanvas_agent_runtime.application.assistant_routing import OrganizationAssistantRoutingService

ROOT = Path(__file__).resolve().parents[1]
GROUPWARE_ENV = "OKCANVAS_GROUPWARE_READ_BEARER"


def test_session_referential_restatement_stays_on_root_without_external_refresh() -> None:
    router = OrganizationAssistantRoutingService(str(ROOT))
    decision = router.route(
        request="앞선 답변에서 확인한 공지 제목만 그대로 다시 말해줘.",
        session_id="session-001",
        tenant_id="tenant-a",
        principal_id="user-001",
        roles=("agent-user",),
    )
    assert decision.request_class == "ANSWER"
    assert decision.status.value == "EXECUTABLE"
    assert decision.selected_agent_id == "organization-assistant-session-agent"
    assert decision.matched_rule_id == "session-referential-restatement-v1"
    assert decision.reasons == (
        "session-reference-detected",
        "restatement-only-language-detected",
        "no-external-refresh-requested",
    )


def test_session_referential_explicit_refresh_still_routes_to_groupware(monkeypatch) -> None:
    monkeypatch.setenv(GROUPWARE_ENV, "connector-secret")
    router = OrganizationAssistantRoutingService(str(ROOT))
    decision = router.route(
        request="앞선 답변의 공지를 다시 조회해서 최신 제목을 알려줘.",
        session_id="session-001",
        tenant_id="tenant-a",
        principal_id="user-001",
        roles=("agent-user",),
    )
    assert decision.request_class == "READ_SYSTEM"
    assert decision.status.value in {"EXECUTABLE", "NOT_CONFIGURED"}
    assert decision.matched_rule_id != "session-referential-restatement-v1"
    assert "groupware-read-intent-detected" in decision.reasons


def test_session_reference_does_not_override_write_or_automation_routing() -> None:
    router = OrganizationAssistantRoutingService(str(ROOT))
    write = router.route(
        request="앞선 답변대로 그룹웨어 공지를 게시해줘.",
        session_id="session-001",
        tenant_id="tenant-a",
        principal_id="user-001",
        roles=("agent-user",),
    )
    assert write.request_class == "WRITE_ACTION"
    assert write.status.value == "PROPOSAL_ONLY"

    automation = router.route(
        request="앞선 답변의 공지 제목을 매일 다시 말해줘.",
        session_id="session-001",
        tenant_id="tenant-a",
        principal_id="user-001",
        roles=("agent-user",),
    )
    assert automation.request_class == "AUTOMATE"
    assert automation.status.value == "PROPOSAL_ONLY"
