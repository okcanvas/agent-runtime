import json
from pathlib import Path

import pytest

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.agent.model.response_storage import (
    ResponseStoragePolicyCatalog,
    ResponseStoragePolicyError,
    build_sdk_response_storage_model_settings_kwargs,
)

ROOT = Path(__file__).resolve().parents[1]


def test_step054_required_files_exist() -> None:
    required = [
        ROOT / "specs/runtime/openai-response-storage-policy.json",
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/response_storage/catalog.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/response_storage/runtime.py"),
        ROOT / "scripts/run_step054_acceptance.py",
        ROOT / "sh_run_step054_acceptance.cmd",
        ROOT / "docs/plans/STEP059_BOUNDED_PROJECT_READONLY_CODING_WORKFLOW.md",
        ROOT / "docs/reference/STEP054_IMMUTABLE_OPENAI_RESPONSE_STORAGE_DISABLED_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP053_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
    ]
    assert all(path.is_file() for path in required)


def test_step054_runtime_info_declares_exact_boundary() -> None:
    info = RuntimeInfo()
    assert info.version == "2.75.0"
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.immutable_reasoning_windows_live_accepted is True
    assert info.immutable_response_storage_policy_implemented is True
    assert info.immutable_response_store_requested is False
    assert info.immutable_response_storage_runtime_binding_bound is True
    assert info.immutable_response_storage_deterministic_accepted is True
    assert info.immutable_response_storage_windows_live_accepted is True


def test_step054_policy_is_exact_and_builds_store_false() -> None:
    policy = ResponseStoragePolicyCatalog(ROOT).resolve()
    assert policy.policy_id == "local-openai-response-storage-disabled-v1"
    assert policy.response_store_requested is False
    assert len(policy.policy_sha256) == 64
    assert build_sdk_response_storage_model_settings_kwargs(policy) == {"store": False}


def test_step054_policy_rejects_store_true(tmp_path: Path) -> None:
    project = tmp_path / "project"
    policy_dir = project / "specs/runtime"
    policy_dir.mkdir(parents=True)
    payload = json.loads((ROOT / "specs/runtime/openai-response-storage-policy.json").read_text())
    payload["response_store_requested"] = True
    (policy_dir / "openai-response-storage-policy.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    with pytest.raises(ResponseStoragePolicyError):
        ResponseStoragePolicyCatalog(project).resolve()


def test_step054_source_contract_is_explicit() -> None:
    gateway = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text()
    binding = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/runtime_binding.py")).read_text()
    acceptance = (ROOT / "scripts/run_step054_acceptance.py").read_text()
    assert "build_sdk_response_storage_model_settings_kwargs" in gateway
    assert '"response_store_requested"' in gateway
    assert '"response_storage_policy": response_storage_policy.to_binding_dict()' in binding
    assert "response_storage_policy_drift_blocked_confirmation" in acceptance
    assert "workspace.finalize(report)" in acceptance
