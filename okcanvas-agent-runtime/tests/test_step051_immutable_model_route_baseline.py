from __future__ import annotations

from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step051_assets_exist() -> None:
    required = [
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/model_routing/catalog.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/model_routing/provider.py"),
        ROOT / "specs/runtime/model-routing-policy.json",
        ROOT / "specs/evaluations/immutable-openai-model-route-v1/case.json",
        ROOT / "scripts/run_step051_acceptance.py",
        ROOT / "sh_run_step051_acceptance.cmd",
        ROOT / "docs/plans/STEP051_IMMUTABLE_OPENAI_MODEL_ROUTE_BINDING_V1.md",
        ROOT / "docs/reference/STEP051_IMMUTABLE_OPENAI_MODEL_ROUTE_BINDING_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP050_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
    ]
    assert all(path.is_file() for path in required)


def test_step051_runtime_info_declares_exact_boundary() -> None:
    info = RuntimeInfo()
    assert info.version == "2.77.0"
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.sqlite_session_mcp_windows_live_accepted is True
    assert info.immutable_model_routing_policy_implemented is True
    assert info.immutable_model_provider_id == "openai"
    assert info.immutable_model_api == "responses"
    assert info.immutable_model_transport == "http"
    assert info.immutable_model_official_base_url_forced is True
    assert info.immutable_model_provider_prefixes_allowed is False
    assert info.immutable_model_automatic_fallback_enabled is False
    assert info.immutable_model_runtime_binding_bound is True
    assert info.immutable_model_provider_close_implemented is True
    assert info.immutable_model_route_deterministic_accepted is True
    assert info.immutable_model_route_windows_live_accepted is True


def test_step051_source_contract_is_explicit() -> None:
    gateway = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text()
    binding = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/runtime_binding.py")).read_text()
    submission = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/run_submission/service.py")).read_text()
    acceptance = (ROOT / "scripts/run_step051_acceptance.py").read_text()
    assert "PinnedOpenAIResponsesProvider" in gateway
    assert "model_provider=model_provider" in gateway
    assert "await model_provider.aclose()" in gateway
    assert '"model_routing_policy": model_policy.to_binding_dict()' in binding
    assert "resolve_model(normalized_model)" in submission
    assert "policy_drift_blocked_confirmation" in acceptance
    assert "workspace.finalize(report)" in acceptance
