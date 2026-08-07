from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.bootstrap.application import create_app
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.transport.service.rest.auth import ServiceClientTokenRegistry

ROOT = Path(__file__).resolve().parents[1]
POLICY_SHA = "3fc4265e1bc75bc8647ca68ee9878aa8c6dc661175198512ac55e6218fa6a5f5"


def test_step069_runtime_and_policy_contract_exact() -> None:
    info = RuntimeInfo()
    assert info.version == "2.75.0"
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.bounded_local_attachment_windows_live_accepted is True
    assert info.multi_user_server_runtime_implemented is True
    assert info.service_client_contract_implemented is True
    assert info.service_client_api_prefix == "/v1/service"
    assert info.service_client_authentication_mode == "bearer-sha256-registry-v1"
    assert info.service_client_resource_scope == "tenant-and-principal"
    assert info.service_client_cross_scope_disclosure_status == 404
    assert info.service_client_native_sdk_stream_exposed is False
    assert info.service_client_runtime_storage_direct_access is False
    assert info.development_tui_is_test_harness is True
    assert info.development_node_cli_is_test_harness is True
    assert info.product_owned_skill_foundation_implemented is True
    assert info.next_selected_step == "UNSELECTED_PENDING_USER_SELECTION"

    policy_path = ROOT / "specs/service_clients/service-client-policy.json"
    assert hashlib.sha256(policy_path.read_bytes()).hexdigest() == POLICY_SHA
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    assert policy["supported_clients"] == ["agent-cli", "agent-web", "agent-desktop"]
    assert policy["roles"] == ["agent-user", "approval-operator"]
    assert policy["owned_resource_types"] == [
        "attachment-slot", "project-snapshot-slot", "session", "submission", "task", "run", "approval"
    ]
    assert policy["native_sdk_stream_exposed"] is False
    assert policy["runtime_storage_direct_access"] is False
    assert policy["skills_available"] is True
    assert policy["skill_catalog_api"] == "/v1/service/skills"
    assert policy["project_snapshot_ingress_enabled"] is True
    assert policy["project_snapshot_api"] == "/v1/service/project-snapshots"
    assert policy["binary_ingress_slot_delete_enabled"] is True
    assert policy["binary_ingress_authenticated_expiry_reconciliation_enabled"] is True
    assert policy["binary_ingress_ownership_failure_compensation_enabled"] is True


def test_service_token_registry_rejects_raw_or_invalid_contracts() -> None:
    token = "service-secret-token"
    valid = {
        "schema_version": "okcanvas-service-client-token-registry-v1",
        "tokens": [{
            "token_id": "web-token",
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "tenant_id": "tenant-a",
            "principal_id": "alice",
            "roles": ["agent-user"],
        }],
    }
    registry = ServiceClientTokenRegistry.from_json_text(json.dumps(valid))
    assert registry.authenticate(token) is not None
    assert registry.authenticate("wrong") is None

    invalid = json.loads(json.dumps(valid))
    invalid["tokens"][0]["raw_token"] = token
    with pytest.raises(ValueError, match="fields are invalid"):
        ServiceClientTokenRegistry.from_json_text(json.dumps(invalid))

    duplicate = json.loads(json.dumps(valid))
    duplicate["tokens"].append(dict(duplicate["tokens"][0]))
    with pytest.raises(ValueError, match="identities must be unique"):
        ServiceClientTokenRegistry.from_json_text(json.dumps(duplicate))


def test_unconfigured_service_auth_fails_closed(tmp_path: Path) -> None:
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key="admin-key-1234567890",
        evaluation_db=tmp_path / "evaluation.sqlite3",
        service_client_token_registry_json=None,
    )
    with TestClient(app) as client:
        response = client.get("/v1/service/capabilities", headers={"Authorization": "Bearer arbitrary"})
    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_CLIENT_AUTH_NOT_CONFIGURED"


def test_future_client_roots_and_development_harness_labels_are_explicit() -> None:
    for client_root in ("clients/cli", "clients/web", "clients/desktop"):
        text = (ROOT / client_root / "README.md").read_text(encoding="utf-8")
        assert "/v1/service" in text
        assert "Runtime" in text
    harness = (ROOT / "clients/cli/README.md").read_text(encoding="utf-8")
    assert "development" in harness.lower()
    assert "acceptance" in harness.lower()
    assert "future multi-user" in harness.lower()


def test_step070_skill_runtime_is_present_and_service_visible() -> None:
    roadmap = (ROOT / "docs/plans/ROADMAP.md").read_text(encoding="utf-8")
    handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
    assert "STEP070_PRODUCT_OWNED_SKILL_PACKAGE_FOUNDATION_V1" in roadmap
    assert "Product-owned Skill" in roadmap
    assert "document-review-v1" in handoff
    assert (legacy_source_contract(ROOT, "okcanvas_agent_runtime/skills")).is_dir()
    assert (ROOT / "specs/skills/document-review-v1/skill.json").is_file()
