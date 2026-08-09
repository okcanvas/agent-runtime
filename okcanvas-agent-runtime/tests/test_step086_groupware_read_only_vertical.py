from __future__ import annotations

import base64
import hashlib
import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.assistant_routing import OrganizationAssistantRoutingService
from okcanvas_agent_runtime.application.groupware_read import (
    GroupwareReadCatalog,
    GroupwareReadState,
)
from okcanvas_agent_runtime.application.mcp_access import DelegatedMCPIdentity
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]
GROUPWARE_ENV = "OKCANVAS_GROUPWARE_READ_BEARER"
ADMIN_KEY = "step086-admin-key-1234567890"
SUBMITTER_KEY = "step086-submitter-key-123456"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_KEY = base64.urlsafe_b64encode(bytes(range(32, 64))).decode("ascii")
USER_TOKEN = "step086-user-service-token-123456"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


REGISTRY = json.dumps(
    {
        "schema_version": "okcanvas-service-client-token-registry-v1",
        "tokens": [
            {
                "token_id": "step086-user",
                "token_sha256": _sha(USER_TOKEN),
                "tenant_id": "tenant-a",
                "principal_id": "alice",
                "roles": ["agent-user"],
            }
        ],
    },
    sort_keys=True,
)


def _configured_project(tmp_path: Path) -> Path:
    project = tmp_path / "configured-project"
    shutil.copytree(ROOT / "specs", project / "specs")
    shutil.copytree(ROOT / "reference", project / "reference")
    server_path = project / "specs/mcp/servers/groupware-read/server.json"
    payload = json.loads(server_path.read_text(encoding="utf-8"))
    payload["url_template"] = "https://groupware.example.com/tenants/{tenant_id}/mcp"
    server_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return project


def _identity(*roles: str) -> DelegatedMCPIdentity:
    return DelegatedMCPIdentity.create(
        tenant_id="tenant-a",
        principal_id="alice",
        roles=roles,
    )


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {USER_TOKEN}"}


def _app(project: Path, tmp_path: Path):
    return create_app(
        project_root=project,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key=ADMIN_KEY,
        run_submitter_key=SUBMITTER_KEY,
        protected_payload_root=tmp_path / "protected-payloads",
        protected_payload_key=PAYLOAD_KEY,
        session_root=tmp_path / "sessions",
        session_history_key=SESSION_KEY,
        service_client_token_registry_json=REGISTRY,
    )


def test_default_groupware_pack_is_strictly_read_only_and_fails_closed(monkeypatch) -> None:
    monkeypatch.delenv(GROUPWARE_ENV, raising=False)
    catalog = GroupwareReadCatalog(ROOT)
    readiness = catalog.readiness(_identity("agent-user"))
    assert readiness.state is GroupwareReadState.NOT_CONFIGURED
    assert readiness.endpoint_configured is False
    assert readiness.credential_reference_configured is True
    assert readiness.credential_value_configured is False
    assert catalog.policy.allowed_tools == (
        "search_notices",
        "search_mail",
        "list_calendar_events",
    )
    assert catalog.policy.max_results == 50
    assert catalog.server.read_only is True
    assert catalog.server.max_retry_attempts == 0
    assert catalog.server.requires_delegated_identity is True
    assert catalog.server.required_roles == ("agent-user",)
    assert catalog.to_public_dict(_identity("agent-user"))["server"]["secret_values_exposed"] is False


def test_configured_groupware_readiness_binds_tenant_principal_role_and_secret_reference(
    tmp_path: Path, monkeypatch
) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(GROUPWARE_ENV, "step086-secret-value")
    catalog = GroupwareReadCatalog(project)
    readiness = catalog.readiness(_identity("agent-user"))
    assert readiness.state is GroupwareReadState.READY
    assert readiness.executable_now is True
    assert readiness.endpoint_configured is True
    assert readiness.credential_reference_configured is True
    assert readiness.credential_value_configured is True
    assert readiness.identity_bound is True
    assert readiness.role_allowed is True
    public = catalog.to_public_dict(_identity("agent-user"))
    assert "step086-secret-value" not in repr(public)
    assert public["server"]["credential_ref"] == "groupware-read-credential"


def test_groupware_readiness_denies_unallowed_role_even_when_endpoint_and_secret_exist(
    tmp_path: Path, monkeypatch
) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(GROUPWARE_ENV, "step086-secret-value")
    readiness = GroupwareReadCatalog(project).readiness(_identity("approval-operator"))
    assert readiness.state is GroupwareReadState.ACCESS_DENIED
    assert readiness.executable_now is False
    assert readiness.identity_bound is True
    assert readiness.role_allowed is False
    assert "delegated-role-not-allowed" in readiness.reasons


def test_groupware_agent_uses_only_v3_read_only_mcp_runtime_binding() -> None:
    definition = AgentDefinitionCatalog(ROOT).resolve("groupware-read-agent")
    assert definition.tools == ()
    assert definition.hosted_tools == ()
    assert definition.agent_tools == ()
    assert definition.handoffs == ()
    assert definition.orchestration_children == ()
    assert definition.mcp_servers == ("groupware-read",)
    assert definition.session_mode == "disabled"
    assert definition.workspace_access == "none"
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    assert binding.execution_path == "multi-remote-mcp-delegated-identity-execution-v1"
    assert len(binding.mcp_servers) == 1
    assert binding.mcp_servers[0]["credential_ref"] == "groupware-read-credential"
    assert binding.mcp_servers[0]["required_roles"] == "agent-user"
    assert binding.mcp_servers[0]["endpoint_mode"] == "tenant-template"


def test_routing_is_groupware_read_specific_without_stealing_draft_or_write_intents(
    tmp_path: Path, monkeypatch
) -> None:
    default_router = OrganizationAssistantRoutingService(str(ROOT))
    default_read = default_router.route(
        request="그룹웨어 공지 목록을 보여줘.",
        tenant_id="tenant-a",
        principal_id="alice",
        roles=("agent-user",),
    )
    assert default_read.request_class == "READ_SYSTEM"
    assert default_read.status.value == "NOT_CONFIGURED"
    assert default_read.selected_agent_id is None
    assert default_read.required_capabilities[0].capability_id == "groupware-read-v1"

    write = default_router.route(
        request="이 메일을 발송해줘.",
        tenant_id="tenant-a",
        principal_id="alice",
        roles=("agent-user",),
    )
    assert write.request_class == "WRITE_ACTION"
    assert write.status.value == "PROPOSAL_ONLY"
    assert write.required_capabilities[0].capability_id == "enterprise-action-write-v1"

    draft = default_router.route(
        request="프로젝트 지연 안내 메일 초안을 작성해줘.",
        tenant_id="tenant-a",
        principal_id="alice",
        roles=("agent-user",),
    )
    assert draft.request_class == "WRITE_CONTENT"
    assert draft.status.value == "EXECUTABLE"
    assert draft.required_capabilities[0].capability_id == "content-drafting-v1"

    project = _configured_project(tmp_path)
    monkeypatch.setenv(GROUPWARE_ENV, "step086-secret-value")
    configured = OrganizationAssistantRoutingService(str(project)).route(
        request="이번 주 내 일정을 보여줘.",
        tenant_id="tenant-a",
        principal_id="alice",
        roles=("agent-user",),
    )
    assert configured.status.value == "EXECUTABLE"
    assert configured.selected_agent_id == "groupware-read-agent"
    assert configured.matched_rule_id == "groupware-read-configured-v1"


def test_groupware_model_context_is_bounded_and_contains_no_endpoint_or_secret(
    tmp_path: Path, monkeypatch
) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(GROUPWARE_ENV, "step086-secret-value")
    router = OrganizationAssistantRoutingService(str(project))
    decision = router.route(
        request="공지 목록을 보여줘.",
        tenant_id="tenant-a",
        principal_id="alice",
        roles=("agent-user",),
    )
    model_request = router.build_model_request(decision, "공지 목록을 보여줘.")
    assert '"groupware_read_policy"' in model_request
    assert '"write_enabled": false' in model_request
    assert '"max_results": 50' in model_request
    assert "groupware.example.com" not in model_request
    assert "groupware-read-credential" not in model_request
    assert "step086-secret-value" not in model_request


def test_service_capabilities_project_principal_specific_groupware_readiness(
    tmp_path: Path, monkeypatch
) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(GROUPWARE_ENV, "step086-secret-value")
    with TestClient(_app(project, tmp_path)) as client:
        response = client.get("/v1/service/capabilities", headers=_headers())
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["groupware_read_foundation_available"] is True
        assert body["groupware_read_state"] == "READY"
        assert body["groupware_read_identity_bound"] is True
        assert body["groupware_read_role_allowed"] is True
        assert body["groupware_read_executable_now"] is True
        assert body["groupware_write_enabled"] is False
        assert "groupware-read-v1" not in body["organization_assistant_unconfigured_capabilities"]


def test_service_preflight_selects_groupware_agent_and_persists_governed_submission(
    tmp_path: Path, monkeypatch
) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(GROUPWARE_ENV, "step086-secret-value")
    with TestClient(_app(project, tmp_path)) as client:
        response = client.post(
            "/v1/service/assistant/run-submissions/preflight",
            headers=_headers(),
            json={
                "input": "최근 공지 목록을 보여줘.",
                "model": "test-model",
                "idempotency_key": "step086-groupware-read-0001",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["route"]["status"] == "EXECUTABLE"
        assert body["route"]["selected_agent_definition_id"] == "groupware-read-agent"
        assert body["submission"]["agent_definition_id"] == "groupware-read-agent"
        assert body["submission"]["state"] == "READY_FOR_CONFIRMATION"
        assert body["submission"]["executable_now"] is True
        payload_files = list((tmp_path / "protected-payloads").glob("*.json"))
        assert len(payload_files) == 1
        encrypted = payload_files[0].read_bytes()
        assert b"step086-secret-value" not in encrypted
        assert b"groupware.example.com" not in encrypted


def test_runtime_info_records_exact_step086_limits_without_claiming_live_enterprise() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.step085_windows_deterministic_accepted is True
    assert info.groupware_read_only_vertical_implemented is True
    assert info.groupware_read_integration_boundary_implemented is True
    assert info.groupware_read_mcp_provider_implemented_in_runtime is False
    assert info.groupware_read_mcp_provider_live_verified is False
    assert info.groupware_read_allowed_tool_count == 3
    assert info.groupware_read_default_state == "NOT_CONFIGURED"
    assert info.groupware_read_real_endpoint_configured is False
    assert info.groupware_read_secret_value_configured is False
    assert info.groupware_read_write_enabled is False
    assert info.groupware_read_durable_automation_enabled is False
    assert info.next_selected_step == "UNSELECTED_PENDING_USER_SELECTION"


def test_step086_windows_entrypoint_registers_acceptance_and_groupware_secret(monkeypatch) -> None:
    from scripts import windows_entrypoint
    import subprocess

    action = next(item for item in windows_entrypoint._parser()._actions if item.dest == "command")
    assert "groupware-readonly-acceptance" in action.choices
    assert "OKCANVAS_GROUPWARE_READ_BEARER" in windows_entrypoint._ALLOWED_KEYS
    parsed = windows_entrypoint.parse_environment_text(
        "OKCANVAS_GROUPWARE_READ_BEARER=metadata-only-runtime-secret",
        source_name="step086-test",
    )
    assert parsed == {"OKCANVAS_GROUPWARE_READ_BEARER": "metadata-only-runtime-secret"}
    captured: dict[str, object] = {}

    def fake_run(command, *, cwd, env, check):
        captured.update(command=command, cwd=cwd, env=env, check=check)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", lambda: ({}, None))
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["groupware-readonly-acceptance"]) == 0
    assert captured["command"][1] == str(ROOT / "scripts/run_step086_acceptance.py")


def test_step086_finalization_preserves_handoff_identities_and_excludes_local_evidence() -> None:
    from scripts.step081_product_inventory import EXCLUDED_PREFIXES, included_relative_path

    handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
    retained_identities = (
        "document-review-v1",
        "local_text_fingerprint",
        "local_text_metrics",
        "project_readonly_inspect",
        "sandbox_project_readonly_inspect",
        "reference-catalog",
    )
    assert all(identity in handoff for identity in retained_identities)
    assert "OR-ISSUE-091" in handoff

    relative = Path("docs/evidence/step086-local/python-regression/chunk-000-019.txt")
    assert ("docs", "evidence", "step086-local") in EXCLUDED_PREFIXES
    assert included_relative_path(relative) is False
    assert "docs/evidence/step086-local/" in (ROOT / ".gitignore").read_text(encoding="utf-8")
