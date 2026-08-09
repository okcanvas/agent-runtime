import json
from pathlib import Path

import pytest

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.agent.model.provider_identity import (
    ProviderIdentifierPolicyCatalog,
    ProviderIdentifierPolicyError,
    minimize_provider_identifier,
    provider_identifier_presence,
)

ROOT = Path(__file__).resolve().parents[1]


def test_step055_required_files_exist() -> None:
    required = [
        ROOT / "specs/runtime/openai-provider-identifier-policy.json",
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/provider_identity/catalog.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/provider_identity/runtime.py"),
        ROOT / "scripts/run_step055_acceptance.py",
        ROOT / "sh_run_step055_acceptance.cmd",
        ROOT / "docs/plans/STEP059_BOUNDED_PROJECT_READONLY_CODING_WORKFLOW.md",
        ROOT / "docs/reference/STEP055_IMMUTABLE_OPENAI_PROVIDER_IDENTIFIER_MINIMIZATION_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP054_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
    ]
    assert all(path.is_file() for path in required)


def test_step055_runtime_info_declares_exact_boundary() -> None:
    info = RuntimeInfo()
    assert info.version == "2.77.0"
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.immutable_response_storage_windows_live_accepted is True
    assert info.immutable_provider_identifier_policy_implemented is True
    assert info.immutable_provider_response_id_persisted is False
    assert info.immutable_provider_request_id_persisted is False
    assert info.immutable_provider_identifier_presence_persisted is True
    assert info.immutable_provider_identifier_runtime_binding_bound is True
    assert info.immutable_provider_identifier_deterministic_accepted is True
    assert info.immutable_provider_identifier_windows_live_accepted is True


def test_step055_policy_is_exact_and_minimizes_identifiers() -> None:
    policy = ProviderIdentifierPolicyCatalog(ROOT).resolve()
    assert policy.policy_id == "local-openai-provider-identifier-minimization-v1"
    assert policy.persist_response_id is False
    assert policy.persist_request_id is False
    assert policy.persist_identifier_presence is True
    assert provider_identifier_presence("resp-private", policy) is True
    assert provider_identifier_presence(None, policy) is False
    assert minimize_provider_identifier("resp-private", policy) is None
    assert len(policy.policy_sha256) == 64


def test_step055_policy_rejects_response_id_persistence(tmp_path: Path) -> None:
    project = tmp_path / "project"
    policy_dir = project / "specs/runtime"
    policy_dir.mkdir(parents=True)
    payload = json.loads(
        (ROOT / "specs/runtime/openai-provider-identifier-policy.json").read_text()
    )
    payload["persist_response_id"] = True
    (policy_dir / "openai-provider-identifier-policy.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    with pytest.raises(ProviderIdentifierPolicyError):
        ProviderIdentifierPolicyCatalog(project).resolve()


def test_step055_source_contract_is_explicit() -> None:
    gateway = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text()
    binding = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/runtime_binding.py")).read_text()
    service = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/service.py")).read_text()
    acceptance = (ROOT / "scripts/run_step055_acceptance.py").read_text()
    assert "minimize_provider_identifier" in gateway
    assert '"response_id_present"' in gateway
    assert '"response_id": getattr(response' not in gateway
    assert '"provider_identifier_policy": provider_identifier_policy.to_binding_dict()' in binding
    assert '"response_id": gateway_result.response_id' in service
    assert "provider_identifier_policy_drift_blocked_confirmation" in acceptance
    assert "workspace.finalize(report)" in acceptance
