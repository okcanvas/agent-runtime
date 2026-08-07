from __future__ import annotations

import base64
import hashlib
import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.application.assistant_routing import OrganizationAssistantRoutingService
from okcanvas_agent_runtime.application.execution import GatewayLifecycleEvent, GenericGatewayRunResult
from okcanvas_agent_runtime.application.organization_context import (
    OrganizationAccessContext,
    OrganizationCatalogState,
    OrganizationContextCatalog,
    OrganizationContextCatalogError,
    OrganizationContextService,
)
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.core.contracts import (
    AssistantCitation,
    AssistantRequestClass,
    AssistantResultStatus,
    AssistantSideEffect,
    OrganizationAssistantResult,
    UsageSummary,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "organization" / "step084-ready"
ADMIN_KEY = "step084-admin-key-1234567890"
SUBMITTER_KEY = "step084-submitter-key-123456"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_KEY = base64.urlsafe_b64encode(bytes(range(32, 64))).decode("ascii")
USER_TOKEN = "step084-user-service-token-123456"
OTHER_TOKEN = "step084-other-service-token-12345"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


REGISTRY = json.dumps(
    {
        "schema_version": "okcanvas-service-client-token-registry-v1",
        "tokens": [
            {
                "token_id": "step084-user",
                "token_sha256": _sha(USER_TOKEN),
                "tenant_id": "step084-tenant",
                "principal_id": "step084-user",
                "roles": ["agent-user"],
            },
            {
                "token_id": "step084-other",
                "token_sha256": _sha(OTHER_TOKEN),
                "tenant_id": "other-tenant",
                "principal_id": "step084-other",
                "roles": ["agent-user"],
            },
        ],
    },
    sort_keys=True,
)


class KnowledgeGateway:
    def __init__(self) -> None:
        self.requests: list[str] = []

    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        self.requests.append(request)
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        await lifecycle_sink(GatewayLifecycleEvent("model.completed", {"response_id": "resp_step084"}))
        await lifecycle_sink(GatewayLifecycleEvent("agent.completed", {"output_contract": definition.output_contract}))
        return GenericGatewayRunResult(
            output=OrganizationAssistantResult(
                status=AssistantResultStatus.ANSWERED,
                answer="이 검증 조직에서 PI는 업무 프로세스 혁신 프로그램을 뜻합니다.",
                request_class=AssistantRequestClass.SEARCH_KNOWLEDGE,
                side_effect=AssistantSideEffect.READ,
                citations=[
                    AssistantCitation(
                        source_type="ORGANIZATION_KNOWLEDGE",
                        label="STEP084 Demo Organization Glossary 2026.08",
                        reference="org://demo/glossary/pi",
                    )
                ],
                completed_actions=[],
                proposed_actions=[],
                pending_approvals=[],
                unverified=[],
                follow_up_state=None,
            ),
            usage=UsageSummary(requests=1, input_tokens=20, output_tokens=12, total_tokens=32),
            trace_id="trace_step084",
            response_id="resp_step084",
            sdk_version="0.19.0",
        )


def _app(tmp_path: Path, *, ready: bool, gateway: KnowledgeGateway | None = None):
    return create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key=ADMIN_KEY,
        gateway=gateway or KnowledgeGateway(),
        run_submitter_key=SUBMITTER_KEY,
        protected_payload_root=tmp_path / "protected-payloads",
        protected_payload_key=PAYLOAD_KEY,
        session_root=tmp_path / "sessions",
        session_history_key=SESSION_KEY,
        service_client_token_registry_json=REGISTRY,
        organization_catalog_root=FIXTURE if ready else None,
    )


def _headers(token: str = USER_TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _wait_terminal(client: TestClient, run_id: str) -> dict:
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers={"X-OKCanvas-Admin-Key": ADMIN_KEY})
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return payload
        time.sleep(0.02)
    raise AssertionError("STEP084 run did not become terminal")


def test_step084_default_catalog_is_valid_empty_and_fails_closed() -> None:
    catalog = OrganizationContextCatalog(ROOT)
    assert catalog.state is OrganizationCatalogState.EMPTY
    assert catalog.record_count == 0
    router = OrganizationAssistantRoutingService(str(ROOT))
    decision = router.route(
        request="우리 회사에서 PI가 무슨 뜻이야?",
        tenant_id="step084-tenant",
        principal_id="step084-user",
        roles=("agent-user",),
    )
    assert decision.status.value == "NOT_CONFIGURED"
    assert decision.grounding_state == "NOT_CONFIGURED"
    assert decision.selected_agent_id is None


def test_step084_ready_catalog_resolves_glossary_knowledge_and_directory_with_scope() -> None:
    service = OrganizationContextService(ROOT, FIXTURE)
    access = OrganizationAccessContext(
        tenant_id="step084-tenant", principal_id="step084-user", roles=("agent-user",)
    )
    glossary = service.glossary("우리 회사에서 PI가 무슨 뜻이야?", access)
    assert glossary.authoritative_match_found is True
    assert glossary.matches[0].record_id == "term.pi"
    assert glossary.matches[0].source_reference == "org://demo/glossary/pi"
    knowledge = service.knowledge("휴가 정책", access)
    assert knowledge.matches[0].record_id == "knowledge.leave-policy"
    directory = service.directory("플랫폼팀장", access)
    assert {item.record_id for item in directory.matches} == {"person.demo-lead", "unit.platform"}

    other = service.combined(
        "PI",
        OrganizationAccessContext(
            tenant_id="other-tenant", principal_id="step084-other", roles=("agent-user",)
        ),
    )
    assert other.matches == ()
    assert other.filtered_count == 4


def test_step084_service_api_and_assistant_preflight_use_authoritative_grounding(tmp_path: Path) -> None:
    gateway = KnowledgeGateway()
    with TestClient(_app(tmp_path, ready=True, gateway=gateway)) as client:
        capabilities = client.get("/v1/service/capabilities", headers=_headers())
        assert capabilities.status_code == 200, capabilities.text
        body = capabilities.json()
        assert body["organization_context_foundation_available"] is True
        assert body["organization_context_catalog_state"] == "READY"
        assert body["organization_context_record_count"] == 4
        assert "organization-knowledge-read-v1" not in body["organization_assistant_unconfigured_capabilities"]

        glossary = client.post(
            "/v1/service/organization/glossary/resolve",
            headers=_headers(),
            json={"query": "PI", "limit": 5},
        )
        assert glossary.status_code == 200, glossary.text
        assert glossary.json()["matches"][0]["record_id"] == "term.pi"

        knowledge = client.post(
            "/v1/service/organization/knowledge/search",
            headers=_headers(),
            json={"query": "휴가 정책"},
        )
        assert knowledge.status_code == 200, knowledge.text
        assert knowledge.json()["matches"][0]["record_id"] == "knowledge.leave-policy"

        directory = client.post(
            "/v1/service/organization/directory/search",
            headers=_headers(),
            json={"query": "플랫폼팀장"},
        )
        assert directory.status_code == 200, directory.text
        assert directory.json()["authoritative_match_found"] is True

        route = client.post(
            "/v1/service/assistant/routes",
            headers=_headers(),
            json={"input": "우리 회사에서 PI가 무슨 뜻이야?"},
        )
        assert route.status_code == 200, route.text
        route_body = route.json()
        assert route_body["schema_version"] == "okcanvas-assistant-route-v2"
        assert route_body["status"] == "EXECUTABLE"
        assert route_body["grounding_state"] == "MATCHED"
        assert route_body["grounding"][0]["record_id"] == "term.pi"

        preflight = client.post(
            "/v1/service/assistant/run-submissions/preflight",
            headers=_headers(),
            json={
                "input": "우리 회사에서 PI가 무슨 뜻이야?",
                "model": "test-model",
                "idempotency_key": "step084-grounded-query-0001",
            },
        )
        assert preflight.status_code == 201, preflight.text
        payload = preflight.json()
        assert payload["schema_version"] == "okcanvas-assistant-run-preflight-v2"
        assert payload["submission"]["agent_definition_id"] == "organization-assistant-agent"
        confirmation = payload["submission"]["confirmation_challenge"]
        confirmed = client.post(
            f"/v1/service/run-submissions/{payload['submission']['submission_id']}/confirm",
            headers=_headers(),
            json={"confirmation": confirmation},
        )
        assert confirmed.status_code == 202, confirmed.text
        assert _wait_terminal(client, confirmed.json()["run_id"])["status"] == "SUCCEEDED"
        assert gateway.requests
        assert '"organization_grounding"' in gateway.requests[0]
        assert "org://demo/glossary/pi" in gateway.requests[0]
        assert '"do_not_infer_unlisted_organization_facts": true' in gateway.requests[0]


def test_step084_no_match_and_cross_tenant_results_do_not_create_model_submission(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path, ready=True)) as client:
        no_match = client.post(
            "/v1/service/assistant/run-submissions/preflight",
            headers=_headers(),
            json={
                "input": "우리 회사에서 존재하지 않는 ZXQ 용어가 무슨 뜻이야?",
                "model": "test-model",
                "idempotency_key": "step084-no-match-query-0001",
            },
        )
        assert no_match.status_code == 201, no_match.text
        assert no_match.json()["route"]["status"] == "NO_MATCH"
        assert no_match.json()["submission"] is None

        cross_tenant = client.post(
            "/v1/service/organization/glossary/resolve",
            headers=_headers(OTHER_TOKEN),
            json={"query": "PI"},
        )
        assert cross_tenant.status_code == 200, cross_tenant.text
        assert cross_tenant.json()["matches"] == []
        assert cross_tenant.json()["filtered_count"] == 1


def test_step084_admin_read_only_queries_require_explicit_scope(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path, ready=True)) as client:
        public_only = client.post(
            "/v1/organization/glossary/resolve",
            headers={"X-OKCanvas-Admin-Key": ADMIN_KEY},
            json={"query": "PI"},
        )
        assert public_only.status_code == 200, public_only.text
        assert public_only.json()["matches"] == []

        scoped = client.post(
            "/v1/organization/glossary/resolve",
            headers={"X-OKCanvas-Admin-Key": ADMIN_KEY},
            json={
                "query": "PI",
                "tenant_id": "step084-tenant",
                "principal_id": "step084-user",
                "roles": ["agent-user"],
            },
        )
        assert scoped.status_code == 200, scoped.text
        assert scoped.json()["matches"][0]["record_id"] == "term.pi"


def test_step084_catalog_hash_drift_fails_closed(tmp_path: Path) -> None:
    copied = tmp_path / "catalog"
    copied.mkdir()
    for source in FIXTURE.iterdir():
        (copied / source.name).write_bytes(source.read_bytes())
    with (copied / "glossary.json").open("a", encoding="utf-8") as handle:
        handle.write(" ")
    try:
        OrganizationContextCatalog(ROOT, copied)
    except OrganizationContextCatalogError as exc:
        assert "hash mismatch" in str(exc)
    else:
        raise AssertionError("Catalog hash drift must fail closed")


def test_step084_acceptance_runtime_info_field_contract_is_exact() -> None:
    info = RuntimeInfo()
    assert info.organization_context_catalog_default_state == "EMPTY"
    source = (ROOT / "scripts/run_step084_acceptance.py").read_text(encoding="utf-8")
    assert "organization_context_catalog_default_state" in source
    assert "organization_context_default_catalog_state" not in source


def test_step084_local_evidence_is_excluded_from_product_inventory() -> None:
    from scripts.step081_product_inventory import EXCLUDED_PREFIXES, included_relative_path

    relative = Path("docs/evidence/step084-local/python-regression/chunk-000-019.txt")
    assert ("docs", "evidence", "step084-local") in EXCLUDED_PREFIXES
    assert included_relative_path(relative) is False
    assert "docs/evidence/step084-local/" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_step084_source_packager_default_identity_is_exact() -> None:
    from scripts.package_source import DEFAULT_OUTPUT, PACKAGE_STEP

    assert PACKAGE_STEP == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert DEFAULT_OUTPUT.name == "okcanvas-agent-runtime-step091d-object-storage-deployment-composition-and-live-acceptance-gate.zip"
