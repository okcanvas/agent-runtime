from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.agent.capabilities.topology import CapabilityFoundationCatalog
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.assistant_routing import OrganizationAssistantRoutingService
from okcanvas_agent_runtime.application.execution.output_registry import resolve_output_contract
from okcanvas_agent_runtime.bootstrap.application import create_app
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.contracts import OrganizationAssistantResult
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

STEP = "STEP083_ORGANIZATION_ASSISTANT_MAIN_AGENT_AND_ACTION_ROUTING_FOUNDATION"
VERSION = "2.63.0"


def _runtime_paths() -> set[str]:
    temp = Path(tempfile.mkdtemp(prefix="okcanvas-step083-routes-"))
    app = create_app(
        project_root=ROOT,
        product_db=temp / "product.sqlite3",
        artifact_root=temp / "artifacts",
        admin_key="step083-validator-admin-key-123456",
        run_submitter_key="step083-validator-submitter-key-123456",
        protected_payload_root=temp / "payloads",
        protected_payload_key=base64.urlsafe_b64encode(bytes(range(32))).decode("ascii"),
        session_root=temp / "sessions",
        session_history_key=base64.urlsafe_b64encode(bytes(range(32, 64))).decode("ascii"),
    )
    return {str(getattr(route, "path", "")) for route in app.routes}


def validate() -> dict[str, object]:
    info = RuntimeInfo()
    definitions = AgentDefinitionCatalog(ROOT)
    all_definitions = definitions.list_definitions()
    one_shot = definitions.resolve("organization-assistant-agent")
    session = definitions.resolve("organization-assistant-session-agent")
    router = OrganizationAssistantRoutingService(str(ROOT))
    policy = router.policy
    foundation = CapabilityFoundationCatalog(ROOT).resolve()
    runtime_paths = _runtime_paths()
    matrix = {
        "general": router.route(request="REST와 이벤트 기반 통합의 차이를 설명해줘."),
        "content": router.route(request="프로젝트 지연 안내 메일 초안을 작성해줘."),
        "knowledge": router.route(request="우리 회사에서 PI가 무슨 뜻이야?"),
        "system_read": router.route(request="내 휴가 잔여일을 알려줘."),
        "write": router.route(request="다음 주 금요일 반차 신청해줘."),
        "automation": router.route(request="매주 월요일 오전 9시에 주간보고를 올려줘."),
        "web": router.route(request="최신 OpenAI 뉴스를 검색해줘."),
    }
    expected_paths = {
        "/v1/assistant/routes",
        "/v1/assistant/run-submissions/preflight",
        "/v1/assistant/sessions",
        "/v1/service/assistant/routes",
        "/v1/service/assistant/run-submissions/preflight",
        "/v1/service/assistant/sessions",
    }
    mcp_allowlist = json.loads((ROOT / "specs/mcp/allowlist.json").read_text(encoding="utf-8"))
    checks = {
        "step083_or_successor_identity_retained": CURRENT_STEP == info.step and PROJECT_VERSION == info.version and CURRENT_STEP in {STEP, "STEP084_ORGANIZATION_KNOWLEDGE_GLOSSARY_AND_DIRECTORY_FOUNDATION"},
        "routing_policy_exact": policy.policy_id == "organization-assistant-routing-v1" and policy.version in {"1.0.0", "1.1.0"},
        "main_agent_catalog_bound": one_shot.output_contract == "OrganizationAssistantResult" and one_shot.session_mode == "disabled",
        "session_agent_catalog_bound": session.output_contract == "OrganizationAssistantResult" and session.session_mode == "sqlite-v1",
        "main_agents_are_language_only": not any((one_shot.tools, one_shot.mcp_servers, one_shot.handoffs, session.tools, session.mcp_servers, session.handoffs)),
        "output_contract_runtime_bound": resolve_output_contract("OrganizationAssistantResult").output_type is OrganizationAssistantResult,
        "agent_catalog_extended_exact": len(all_definitions) >= 29 and foundation.agent_topology_count >= 29 and foundation.binding_count >= 34,
        "general_and_content_routes_executable": matrix["general"].request_class == "ANSWER" and matrix["general"].executable_now and matrix["content"].request_class == "WRITE_CONTENT" and matrix["content"].executable_now,
        "organization_knowledge_fails_closed": matrix["knowledge"].request_class == "SEARCH_KNOWLEDGE" and matrix["knowledge"].status.value == "NOT_CONFIGURED" and not matrix["knowledge"].executable_now,
        "enterprise_read_fails_closed": matrix["system_read"].request_class == "READ_SYSTEM" and matrix["system_read"].status.value == "NOT_CONFIGURED" and not matrix["system_read"].executable_now,
        "write_is_proposal_only": matrix["write"].request_class == "WRITE_ACTION" and matrix["write"].status.value == "PROPOSAL_ONLY" and matrix["write"].selected_agent_id == "organization-assistant-agent",
        "automation_is_proposal_only": matrix["automation"].request_class == "AUTOMATE" and matrix["automation"].status.value == "PROPOSAL_ONLY" and matrix["automation"].selected_agent_id == "organization-assistant-agent",
        "public_web_route_reuses_accepted_agent": matrix["web"].request_class == "SEARCH_WEB" and matrix["web"].selected_agent_id == "hosted-web-search-agent",
        "attachment_and_snapshot_routes_exact": router.route(request="첨부 검토", attachment_id="attachment_slot_" + "a" * 32).selected_agent_id == "local-document-review-agent" and router.route(request="코드 분석", project_snapshot_id="project_snapshot_slot_" + "b" * 32).selected_agent_id == "sandbox-readonly-coding-agent",
        "assistant_routes_registered": expected_paths.issubset(runtime_paths),
        "tool_search_still_disabled": foundation.discovery_policy.tool_search_runtime_enabled is False and foundation.discovery_policy.programmatic_tool_calling_runtime_enabled is False,
        "enterprise_mcp_not_falsely_configured": mcp_allowlist.get("allowed_server_ids") == ["reference-catalog"],
        "next_step_exact": info.next_selected_step in {"STEP084_ORGANIZATION_KNOWLEDGE_GLOSSARY_AND_DIRECTORY_FOUNDATION", "STEP085_MULTI_MCP_AND_DELEGATED_IDENTITY_FOUNDATION"},
    }
    return {
        "schema_version": "okcanvas-step083-assistant-routing-validation-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(checks.values()),
        "total_checks": len(checks),
        "policy_sha256": policy.policy_sha256,
        "agent_definition_count": len(all_definitions),
        "capability_binding_count": foundation.binding_count,
        "runtime_assistant_routes": sorted(expected_paths & runtime_paths),
        "routing_matrix": {key: value.to_public_dict() for key, value in matrix.items()},
    }


if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if result["state"] == "PASSED" else 1)
