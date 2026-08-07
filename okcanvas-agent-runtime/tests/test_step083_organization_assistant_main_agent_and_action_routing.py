from __future__ import annotations

import base64
import hashlib
import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.assistant_routing import OrganizationAssistantRoutingService
from okcanvas_agent_runtime.application.execution import GatewayLifecycleEvent, GenericGatewayRunResult
from okcanvas_agent_runtime.application.execution.output_registry import resolve_output_contract
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.core.contracts import (
    AssistantRequestClass,
    AssistantResultStatus,
    AssistantSideEffect,
    OrganizationAssistantResult,
    UsageSummary,
)

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step083-admin-key-1234567890"
SUBMITTER_KEY = "step083-submitter-key-123456"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_KEY = base64.urlsafe_b64encode(bytes(range(32, 64))).decode("ascii")
USER_TOKEN = "step083-user-service-token-123456"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


REGISTRY = json.dumps(
    {
        "schema_version": "okcanvas-service-client-token-registry-v1",
        "tokens": [
            {
                "token_id": "step083-user",
                "token_sha256": _sha(USER_TOKEN),
                "tenant_id": "step083-tenant",
                "principal_id": "step083-user",
                "roles": ["agent-user"],
            }
        ],
    },
    sort_keys=True,
)


class AssistantGateway:
    def __init__(self) -> None:
        self.requests: list[str] = []

    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        self.requests.append(request)
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        await lifecycle_sink(GatewayLifecycleEvent("model.completed", {"response_id": "resp_step083"}))
        await lifecycle_sink(
            GatewayLifecycleEvent("agent.completed", {"output_contract": definition.output_contract})
        )
        return GenericGatewayRunResult(
            output=OrganizationAssistantResult(
                status=AssistantResultStatus.ANSWERED,
                answer="REST is request-response; event integration decouples producers and consumers.",
                request_class=AssistantRequestClass.ANSWER,
                side_effect=AssistantSideEffect.NONE,
                citations=[],
                completed_actions=[],
                proposed_actions=[],
                pending_approvals=[],
                unverified=[],
                follow_up_state=None,
            ),
            usage=UsageSummary(requests=1, input_tokens=10, output_tokens=8, total_tokens=18),
            trace_id="trace_step083",
            response_id="resp_step083",
            sdk_version="0.19.0",
        )


def _app(tmp_path: Path, gateway: AssistantGateway | None = None):
    return create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key=ADMIN_KEY,
        gateway=gateway or AssistantGateway(),
        run_submitter_key=SUBMITTER_KEY,
        protected_payload_root=tmp_path / "protected-payloads",
        protected_payload_key=PAYLOAD_KEY,
        session_root=tmp_path / "sessions",
        session_history_key=SESSION_KEY,
        service_client_token_registry_json=REGISTRY,
    )


def _service_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {USER_TOKEN}"}


def _wait_terminal(client: TestClient, run_id: str) -> dict:
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers={"X-OKCanvas-Admin-Key": ADMIN_KEY})
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return payload
        time.sleep(0.02)
    raise AssertionError("STEP083 run did not become terminal")


def test_step083_main_agent_definitions_and_output_contract_are_catalog_bound() -> None:
    definitions = AgentDefinitionCatalog(ROOT)
    one_shot = definitions.resolve("organization-assistant-agent")
    session = definitions.resolve("organization-assistant-session-agent")
    assert one_shot.output_contract == session.output_contract == "OrganizationAssistantResult"
    assert one_shot.session_mode == "disabled"
    assert session.session_mode == "sqlite-v1"
    assert one_shot.tools == one_shot.mcp_servers == one_shot.handoffs == ()
    assert session.tools == session.mcp_servers == session.handoffs == ()
    assert resolve_output_contract("OrganizationAssistantResult").output_type is OrganizationAssistantResult
    assert one_shot.output_schema == OrganizationAssistantResult.model_json_schema()
    assert session.output_schema == OrganizationAssistantResult.model_json_schema()


def test_step083_deterministic_routing_matrix_is_safety_first() -> None:
    router = OrganizationAssistantRoutingService(str(ROOT))
    cases = {
        "REST와 이벤트 기반 통합의 차이를 설명해줘.": ("ANSWER", "EXECUTABLE", "organization-assistant-agent"),
        "프로젝트 지연 안내 메일 초안을 작성해줘.": ("WRITE_CONTENT", "EXECUTABLE", "organization-assistant-agent"),
        "우리 회사에서 PI가 무슨 뜻이야?": ("SEARCH_KNOWLEDGE", "NOT_CONFIGURED", None),
        "내 휴가 잔여일을 알려줘.": ("READ_SYSTEM", "NOT_CONFIGURED", None),
        "다음 주 금요일 반차 신청해줘.": ("WRITE_ACTION", "PROPOSAL_ONLY", "organization-assistant-agent"),
        "매주 월요일 오전 9시에 주간보고를 올려줘.": ("AUTOMATE", "PROPOSAL_ONLY", "organization-assistant-agent"),
        "최신 OpenAI 뉴스를 검색해줘.": ("SEARCH_WEB", "EXECUTABLE", "hosted-web-search-agent"),
    }
    for request, expected in cases.items():
        decision = router.route(request=request)
        assert (decision.request_class, decision.status.value, decision.selected_agent_id) == expected
    attachment = router.route(
        request="이 첨부파일을 검토해줘.",
        attachment_id="attachment_slot_" + "a" * 32,
    )
    assert attachment.request_class == "ANALYZE_ATTACHMENT"
    assert attachment.selected_agent_id == "local-document-review-agent"
    snapshot = router.route(
        request="재고 계산식을 찾아줘.",
        project_snapshot_id="project_snapshot_slot_" + "b" * 32,
    )
    assert snapshot.request_class == "CODE_ASSIST"
    assert snapshot.selected_agent_id == "sandbox-readonly-coding-agent"


def test_step083_service_exposes_agent_id_free_route_preflight_and_session(tmp_path: Path) -> None:
    gateway = AssistantGateway()
    with TestClient(_app(tmp_path, gateway)) as client:
        headers = _service_headers()
        capabilities = client.get("/v1/service/capabilities", headers=headers)
        assert capabilities.status_code == 200, capabilities.text
        cap = capabilities.json()
        assert cap["organization_assistant_routing_available"] is True
        assert cap["organization_assistant_default_agent_id"] == "organization-assistant-agent"
        assert "enterprise-system-read-v1" in cap["organization_assistant_unconfigured_capabilities"]

        route = client.post(
            "/v1/service/assistant/routes",
            headers=headers,
            json={"input": "우리 회사에서 PI가 무슨 뜻이야?"},
        )
        assert route.status_code == 200, route.text
        assert route.json()["status"] == "NOT_CONFIGURED"
        assert route.json()["selected_agent_definition_id"] is None

        unavailable = client.post(
            "/v1/service/assistant/run-submissions/preflight",
            headers=headers,
            json={
                "input": "내 휴가 잔여일을 알려줘.",
                "model": "test-model",
                "idempotency_key": "step083-unavailable-0001",
            },
        )
        assert unavailable.status_code == 201, unavailable.text
        assert unavailable.json()["route"]["request_class"] == "READ_SYSTEM"
        assert unavailable.json()["submission"] is None

        preflight = client.post(
            "/v1/service/assistant/run-submissions/preflight",
            headers=headers,
            json={
                "input": "REST와 이벤트 기반 통합의 차이를 설명해줘.",
                "model": "test-model",
                "idempotency_key": "step083-general-answer-0001",
            },
        )
        assert preflight.status_code == 201, preflight.text
        payload = preflight.json()
        assert payload["route"]["request_class"] == "ANSWER"
        assert payload["submission"]["agent_definition_id"] == "organization-assistant-agent"
        assert payload["submission"]["confirmation_challenge"]

        session = client.post("/v1/service/assistant/sessions", headers=headers)
        assert session.status_code == 201, session.text
        assert session.json()["agent_definition_id"] == "organization-assistant-session-agent"
        session_route = client.post(
            "/v1/service/assistant/routes",
            headers=headers,
            json={
                "input": "앞의 설명을 한 문장으로 줄여줘.",
                "session_id": session.json()["session_id"],
            },
        )
        assert session_route.status_code == 200, session_route.text
        assert session_route.json()["selected_agent_definition_id"] == "organization-assistant-session-agent"

        confirmation = payload["submission"]["confirmation_challenge"]
        confirmed = client.post(
            f"/v1/service/run-submissions/{payload['submission']['submission_id']}/confirm",
            headers=headers,
            json={"confirmation": confirmation},
        )
        assert confirmed.status_code == 202, confirmed.text
        terminal = _wait_terminal(client, confirmed.json()["run_id"])
        assert terminal["status"] == "SUCCEEDED"
        assert gateway.requests
        assert gateway.requests[0].startswith("OKCANVAS ROUTING CONTEXT (product-owned, immutable):")
        assert '"request_class": "ANSWER"' in gateway.requests[0]


def test_step083_admin_route_parity_and_project_snapshot_binding(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        headers = {
            "X-OKCanvas-Admin-Key": ADMIN_KEY,
            "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
        }
        route = client.post(
            "/v1/assistant/routes",
            headers={"X-OKCanvas-Admin-Key": ADMIN_KEY},
            json={
                "input": "업로드한 프로젝트의 함수를 분석해줘.",
                "project_snapshot_id": "project_snapshot_slot_" + "c" * 32,
            },
        )
        assert route.status_code == 200, route.text
        assert route.json()["selected_agent_definition_id"] == "sandbox-readonly-coding-agent"
        session = client.post("/v1/assistant/sessions", headers=headers)
        assert session.status_code == 201, session.text
        assert session.json()["agent_definition_id"] == "organization-assistant-session-agent"

def test_step083_local_evidence_is_excluded_from_product_inventory() -> None:
    from scripts.step081_product_inventory import EXCLUDED_PREFIXES, included_relative_path

    relative = Path("docs/evidence/step083-local/python-regression/chunk-000-019.txt")
    assert ("docs", "evidence", "step083-local") in EXCLUDED_PREFIXES
    assert included_relative_path(relative) is False
    assert "docs/evidence/step083-local/" in (ROOT / ".gitignore").read_text(encoding="utf-8")

