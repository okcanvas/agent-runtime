from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.bootstrap.application import create_app
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.adapters.sandbox.docker import (
    SandboxProviderContractError,
    SandboxRuntimeCatalog,
    SandboxRuntimePolicyError,
)

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "reference/upstream/openai-agents-python-0.19.0/src/agents/sandbox"
SOURCE_HASHES = {
    "capabilities/capabilities.py": "7a40308ac95dd8f649bc06047af0d7183b76338120ec6453acef9991f9d1d406",
    "capabilities/filesystem.py": "9810f7878518c708c16a2b55a2748b84eabeb0c106e7d223d6b52088c1bbf3f3",
    "capabilities/shell.py": "0ddacb568dde2fe06eaea61f8ffe97f5556d0f3aea73693996888bc87331cfbf",
    "sandbox_agent.py": "8e90f64f1c5a3e9ae062c490300c9f6d1fa49958873c0c05a440c184b8ee18be",
    "sandboxes/docker.py": "8f1cc63295eee21b2a78b85f17082586c7be6e4ac4f4504d187e0eb672d2eb35",
}


def _registry() -> str:
    return json.dumps(
        {
            "schema_version": "okcanvas-service-client-token-registry-v1",
            "tokens": [
                {
                    "token_id": "step073-user",
                    "token_sha256": hashlib.sha256(b"step073-token").hexdigest(),
                    "tenant_id": "tenant-step073",
                    "principal_id": "principal-step073",
                    "roles": ["agent-user"],
                }
            ],
        }
    )


def _headers() -> dict[str, str]:
    return {"Authorization": "Bearer step073-token"}


def test_step073_windows_acceptance_is_closed_as_predecessor() -> None:
    evidence = json.loads(
        (ROOT / "docs/evidence/STEP073_WINDOWS_ACCEPTANCE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert evidence["step"] == "STEP073_PRODUCT_OWNED_SANDBOX_RUNTIME_FOUNDATION_V1"
    assert evidence["version"] == "2.53.0"
    assert evidence["state"] == "PASSED"
    assert evidence["passed_checks"] == evidence["total_checks"] == 26
    assert evidence["agent_definition_count"] == 26
    assert evidence["docker_calls"] == 0
    assert evidence["external_network_calls"] == 0
    assert evidence["model_calls"] == 0


def test_current_runtime_preserves_step073_foundation_under_step075() -> None:
    info = RuntimeInfo()
    assert info.version == "2.75.0"
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.product_owned_sandbox_runtime_foundation_implemented is True
    assert info.product_owned_sandbox_foundation_deterministic_accepted is True
    assert info.product_owned_sandbox_foundation_windows_accepted is True
    assert info.product_owned_sandbox_execution_enabled is True
    assert info.product_owned_docker_lifecycle_windows_live_accepted is True
    assert info.next_selected_step == "UNSELECTED_PENDING_USER_SELECTION"


def test_step073_declared_modes_are_preserved_and_only_readonly_is_newly_active() -> None:
    foundation = SandboxRuntimeCatalog(ROOT).resolve()
    assert foundation.policy.declared_workspace_access_modes == (
        "none",
        "sandbox-readonly-v1",
        "sandbox-patch-v1",
        "sandbox-shell-v1",
    )
    assert foundation.policy.active_workspace_access_modes == ("none", "sandbox-readonly-v1")
    assert foundation.policy.agent_execution_enabled is True
    assert foundation.policy.physical_workspace_materialization_enabled is True
    assert foundation.policy.shell_enabled is False
    assert foundation.policy.apply_patch_enabled is False


def test_original_step073_agents_remain_workspace_none() -> None:
    definitions = AgentDefinitionCatalog(ROOT).list_definitions()
    assert len(definitions) == 32
    original = [item for item in definitions if item.agent_id != "sandbox-readonly-coding-agent"]
    assert {item.workspace_access for item in original} == {"none"}
    bindings = [AgentRuntimeBindingCatalog(ROOT).resolve(item) for item in definitions]
    assert len({item.sandbox_runtime_foundation["foundation_sha256"] for item in bindings}) == 1


def test_unknown_policy_field_fails_closed(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs/sandbox", project / "specs/sandbox")
    path = project / "specs/sandbox/policies/default-sandbox-runtime-policy.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SandboxRuntimePolicyError):
        SandboxRuntimeCatalog(project).resolve()


def test_unsafe_provider_capability_fails_closed(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs/sandbox", project / "specs/sandbox")
    path = project / "specs/sandbox/providers/docker-local-v1/provider.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["cap_add"] = ["SYS_ADMIN"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises((SandboxRuntimePolicyError, SandboxProviderContractError)):
        SandboxRuntimeCatalog(project).resolve()


def test_symbolic_policy_path_is_rejected_when_supported(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs/sandbox", project / "specs/sandbox")
    policy = project / "specs/sandbox/policies/default-sandbox-runtime-policy.json"
    target = tmp_path / "outside.json"
    target.write_bytes(policy.read_bytes())
    policy.unlink()
    try:
        os.symlink(target, policy)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable")
    with pytest.raises(SandboxRuntimePolicyError):
        SandboxRuntimeCatalog(project).resolve()


def test_retained_sdk_sandbox_audit_hashes_remain_exact() -> None:
    for relative, expected in SOURCE_HASHES.items():
        assert hashlib.sha256((UPSTREAM / relative).read_bytes()).hexdigest() == expected
    capabilities = (UPSTREAM / "capabilities/capabilities.py").read_text(encoding="utf-8")
    filesystem = (UPSTREAM / "capabilities/filesystem.py").read_text(encoding="utf-8")
    docker = (UPSTREAM / "sandboxes/docker.py").read_text(encoding="utf-8")
    assert "return [Filesystem(), Shell(), Compaction()]" in capabilities
    assert "SandboxApplyPatchTool" in filesystem
    assert "self.docker_client.images.pull" in docker
    assert 'cap_add=["SYS_ADMIN"]' in docker


def test_product_source_still_does_not_import_sdk_sandbox() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "okcanvas_agent_runtime").rglob("*.py"))
    )
    assert "from agents.sandbox" not in source
    assert "import agents.sandbox" not in source
    assert "DockerSandboxClient(" not in source


def test_service_metadata_remains_authenticated_and_contains_no_image_value(tmp_path: Path) -> None:
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key="step073-admin-key-value",
        run_submitter_key="step073-submitter-key-value",
        protected_payload_root=tmp_path / "payloads",
        protected_payload_key="11" * 32,
        session_root=tmp_path / "sessions",
        session_history_key="22" * 32,
        service_client_token_registry_json=_registry(),
    )
    with TestClient(app) as client:
        assert client.get("/v1/service/sandbox-runtime").status_code == 401
        response = client.get("/v1/service/sandbox-runtime", headers=_headers())
        assert response.status_code == 200
        payload = response.json()
        assert payload["agent_execution_enabled"] is True
        assert payload["active_workspace_access_modes"] == ["none", "sandbox-readonly-v1"]
        assert "requested_reference" not in payload
        assert "immutable_reference" not in payload
        assert "runtime_image" not in payload
