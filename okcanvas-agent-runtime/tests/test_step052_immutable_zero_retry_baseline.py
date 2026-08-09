from __future__ import annotations

from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step052_assets_exist() -> None:
    required = [
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/model_retry/catalog.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/model_retry/runtime.py"),
        ROOT / "specs/runtime/model-retry-policy.json",
        ROOT / "specs/evaluations/immutable-openai-zero-retry-v1/case.json",
        ROOT / "scripts/run_step052_acceptance.py",
        ROOT / "sh_run_step052_acceptance.cmd",
        ROOT / "docs/plans/STEP052_IMMUTABLE_OPENAI_ZERO_RETRY_POLICY_V1.md",
        ROOT / "docs/reference/STEP052_IMMUTABLE_OPENAI_ZERO_RETRY_POLICY_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP051_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
    ]
    assert all(path.is_file() for path in required)


def test_step052_runtime_info_declares_exact_boundary() -> None:
    info = RuntimeInfo()
    assert info.version == "2.77.0"
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.immutable_model_route_windows_live_accepted is True
    assert info.immutable_model_retry_policy_implemented is True
    assert info.immutable_model_runner_managed_max_retries == 0
    assert info.immutable_model_provider_managed_max_retries == 0
    assert info.immutable_model_conversation_locked_compatibility_retries is False
    assert info.immutable_model_retryable_category_count == 0
    assert info.immutable_model_retry_runtime_binding_bound is True
    assert info.immutable_model_retry_deterministic_accepted is True
    assert info.immutable_model_retry_windows_live_accepted is True


def test_step052_source_contract_is_explicit() -> None:
    gateway = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text()
    provider = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/model_routing/provider.py")).read_text()
    binding = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/runtime_binding.py")).read_text()
    acceptance = (ROOT / "scripts/run_step052_acceptance.py").read_text()
    assert "build_sdk_model_retry_settings" in gateway
    assert "model_settings=ModelSettings(retry=model_retry_settings, **reasoning_settings, **response_storage_settings)" in gateway
    assert "max_retries=self.retry_policy.provider_managed_max_retries" in provider
    assert '"model_retry_policy": model_retry_policy.to_binding_dict()' in binding
    assert "retry_policy_drift_blocked_confirmation" in acceptance
    assert "workspace.finalize(report)" in acceptance
