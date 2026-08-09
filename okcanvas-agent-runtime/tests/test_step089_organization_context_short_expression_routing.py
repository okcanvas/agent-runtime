from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from okcanvas_agent_protocols.rest.admin import AssistantRouteResponse
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.execution.output_registry import list_output_contracts

from okcanvas_agent_runtime.application.assistant_routing import (
    AssistantRoutingPolicyCatalog,
    AssistantRoutingPolicyError,
    OrganizationAssistantRoutingService,
)
from scripts.package_source import DEFAULT_OUTPUT, PACKAGE_STEP

ROOT = Path(__file__).resolve().parents[1]
ORG_CONTEXT_ENV = "OKCANVAS_ORGANIZATION_CONTEXT_READ_BEARER"
STEP = "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"


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


def test_step089_short_read_policy_contract_is_exact_and_product_owned() -> None:
    policy = AssistantRoutingPolicyCatalog(ROOT).resolve()
    assert policy.version == "1.5.0"
    assert len(policy.organization_context_short_read_rules) == 4
    assert [item.pattern_id for item in policy.organization_context_short_read_rules] == [
        "organization-context-entity-detail-short-v1",
        "organization-context-contact-field-short-v1",
        "organization-context-position-field-short-v1",
        "organization-context-position-members-short-v1",
    ]
    assert policy.match_organization_context_short_read("김민수 정보") is not None
    assert policy.match_organization_context_short_read("김선임 연락처") is not None
    assert policy.match_organization_context_short_read("김민수 직책") is not None
    assert policy.match_organization_context_short_read("과장들 목록") is not None


def test_step089_short_expression_routes_to_existing_organization_context_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(ORG_CONTEXT_ENV, "connector-secret")
    router = OrganizationAssistantRoutingService(str(project))
    cases = {
        "김민수 정보": (
            "organization-context-entity-detail-short-v1",
            "ENTITY_DETAIL_LOOKUP",
            "김민수",
            [],
            ["DETAIL"],
            "RESOLVE",
        ),
        "김선임 연락처": (
            "organization-context-contact-field-short-v1",
            "ENTITY_FIELD_LOOKUP",
            "김선임",
            [],
            ["CONTACT"],
            "RESOLVE",
        ),
        "김민수 직책": (
            "organization-context-position-field-short-v1",
            "ENTITY_FIELD_LOOKUP",
            "김민수",
            [],
            ["POSITION"],
            "RESOLVE",
        ),
        "과장들 목록": (
            "organization-context-position-members-short-v1",
            "ENTITY_LIST_BY_POSITION",
            "과장",
            ["POSITION", "EMPLOYEE"],
            ["MEMBERS"],
            "SEARCH",
        ),
    }
    for request, expected in cases.items():
        decision = router.route(
            request=request,
            session_id="session-001",
            tenant_id="tenant-a",
            principal_id="alice",
            roles=("agent-user",),
        )
        assert decision.request_class == "SEARCH_KNOWLEDGE"
        assert decision.status.value == "EXECUTABLE"
        assert decision.selected_agent_id == "organization-context-session-agent"
        assert decision.required_capabilities[0].selected_agent_id == (
            "organization-context-read-agent"
        )
        assert decision.matched_rule_id == (
            "organization-context-short-read-session-stateless-subagent-v1"
        )
        hint = decision.organization_context_request_hint
        assert hint is not None
        assert (
            hint.pattern_id,
            hint.intent,
            hint.target_expression,
            list(hint.entity_type_hints),
            list(hint.requested_fields),
            hint.preferred_operation.value,
        ) == expected
        public = AssistantRouteResponse(**decision.to_public_dict())
        assert public.organization_context_request_hint is not None
        assert public.organization_context_request_hint.target_expression == expected[2]
        model_request = router.build_model_request(decision, request)
        assert '"routing_only": true' in model_request
        assert '"not_entity_evidence": true' in model_request
        assert '"tool_result_remains_authoritative": true' in model_request
        assert "connector-secret" not in model_request


def test_step089_short_expression_fails_closed_when_remote_context_is_not_configured() -> None:
    router = OrganizationAssistantRoutingService(str(ROOT))
    decision = router.route(
        request="김민수 정보",
        tenant_id="tenant-a",
        principal_id="alice",
        roles=("agent-user",),
    )
    assert decision.status.value == "NOT_CONFIGURED"
    assert decision.selected_agent_id is None
    assert decision.matched_rule_id == "organization-context-short-read-not-configured-v1"
    assert decision.organization_context_request_hint is not None
    assert decision.organization_context_request_hint.target_expression == "김민수"


def test_step089_short_expression_negative_cases_do_not_enter_organization_context() -> None:
    router = OrganizationAssistantRoutingService(str(ROOT))
    cases = {
        "김민수라는 이름으로 소설 써줘": "WRITE_CONTENT",
        "과장이란 단어의 어원은?": "ANSWER",
        "연락처를 잘 관리하는 방법": "ANSWER",
        "팀워크가 중요한 이유": "ANSWER",
    }
    for request, expected_class in cases.items():
        decision = router.route(request=request)
        assert decision.request_class == expected_class
        assert decision.organization_context_request_hint is None
        assert not decision.matched_rule_id.startswith("organization-context-short-read")


def test_step089_short_read_does_not_create_main_or_sub_agent_skills() -> None:
    definitions = AgentDefinitionCatalog(ROOT)
    root = definitions.resolve("organization-context-session-agent")
    child = definitions.resolve("organization-context-read-agent")
    assert root.skills == ()
    assert child.skills == ()
    assert root.agent_tools == ("organization-context-read-agent",)
    assert child.mcp_servers == ("organization-context-read",)


def test_step089_short_read_policy_rejects_duplicate_suffix(tmp_path: Path) -> None:
    project = tmp_path / "invalid-project"
    shutil.copytree(ROOT / "specs", project / "specs")
    policy_path = project / "specs/assistant/routing-policy.json"
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    payload["organization_context_short_read_rules"][1]["suffixes"] = [" 정보"]
    policy_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(AssistantRoutingPolicyError, match="globally unique"):
        AssistantRoutingPolicyCatalog(project).resolve()


def test_step089_source_packager_identity_and_default_output_are_current() -> None:
    assert PACKAGE_STEP == STEP
    assert DEFAULT_OUTPUT.name == (
        "okcanvas-agent-runtime-step093-relation-aware-contextual-follow-up-and-evidence-bound-traversal.zip"
    )


def test_step089_current_output_contract_inventory_is_complete() -> None:
    contract_names = {contract.contract_name for contract in list_output_contracts()}
    assert contract_names == {
        "BoundedOrchestrationResult",
        "CodingAgentResult",
        "GroupwareReadResult",
        "HostedWebSearchResult",
        "LocalDocumentReviewResult",
        "OrganizationAssistantResult",
        "OrganizationContextReadResult",
        "StoreReplenishmentReviewResult",
    }
