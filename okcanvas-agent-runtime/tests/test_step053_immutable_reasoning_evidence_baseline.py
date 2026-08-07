from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step053_required_files_exist() -> None:
    required = [
        ROOT / "specs/runtime/reasoning-evidence-policy.json",
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/reasoning_evidence/catalog.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/reasoning_evidence/runtime.py"),
        ROOT / "scripts/run_step053_acceptance.py",
        ROOT / "sh_run_step053_acceptance.cmd",
        ROOT / "docs/plans/STEP059_BOUNDED_PROJECT_READONLY_CODING_WORKFLOW.md",
        ROOT / "docs/reference/STEP053_IMMUTABLE_REASONING_EVIDENCE_MINIMIZATION_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP052_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
    ]
    assert all(path.is_file() for path in required)


def test_step053_runtime_info_declares_exact_boundary() -> None:
    info = RuntimeInfo()
    assert info.version == "2.75.0"
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.immutable_model_retry_windows_live_accepted is True
    assert info.immutable_reasoning_evidence_policy_implemented is True
    assert info.immutable_reasoning_summary_requested is False
    assert info.immutable_reasoning_response_include_count == 0
    assert info.immutable_reasoning_content_persisted is False
    assert info.immutable_reasoning_summary_persisted is False
    assert info.immutable_reasoning_item_ids_persisted is False
    assert info.immutable_reasoning_provider_data_persisted is False
    assert info.immutable_reasoning_token_count_persisted is True
    assert info.immutable_reasoning_runtime_binding_bound is True
    assert info.immutable_reasoning_deterministic_accepted is True
    assert info.immutable_reasoning_windows_live_accepted is True


def test_step053_source_contract_is_explicit() -> None:
    gateway = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text()
    binding = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/runtime_binding.py")).read_text()
    acceptance = (ROOT / "scripts/run_step053_acceptance.py").read_text()
    assert "build_sdk_reasoning_model_settings_kwargs" in gateway
    assert "reasoning_item_count" in gateway
    assert "reasoning_content_persisted" in gateway
    assert '"reasoning_evidence_policy": reasoning_evidence_policy.to_binding_dict()' in binding
    assert "reasoning_policy_drift_blocked_confirmation" in acceptance
    assert "workspace.finalize(report)" in acceptance
