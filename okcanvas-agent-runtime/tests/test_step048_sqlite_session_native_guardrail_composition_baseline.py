from __future__ import annotations

from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step048_assets_exist() -> None:
    required = [
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/sessions/guardrail_policy.py"),
        ROOT / "specs/runtime/sqlite-session-guardrail-policy.json",
        ROOT / "specs/agents/session-guardrail-language-agent/definition.json",
        ROOT / "specs/evaluations/sqlite-session-native-guardrail-v1/case.json",
        ROOT / "scripts/run_step048_acceptance.py",
        ROOT / "sh_run_step048_acceptance.cmd",
        ROOT / "docs/plans/STEP048_SQLITE_SESSION_NATIVE_GUARDRAIL_COMPOSITION_V1.md",
        ROOT / "docs/reference/STEP048_SQLITE_SESSION_NATIVE_GUARDRAIL_COMPOSITION_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP047_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
    ]
    assert all(path.is_file() for path in required)


def test_step048_runtime_info_declares_exact_boundary() -> None:
    info = RuntimeInfo()
    assert info.version == "2.77.0"
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.sqlite_session_handoff_windows_live_accepted is True
    assert info.sqlite_session_guardrail_composition_implemented is True
    assert info.sqlite_session_guardrail_allowed_kinds == "INPUT,OUTPUT"
    assert info.sqlite_session_guardrail_max_per_kind == 1
    assert info.sqlite_session_guardrail_tripped_turn_rolled_back is True
    assert info.sqlite_session_guardrail_raw_history_persisted_in_product_events is False
    assert info.sqlite_session_guardrail_deterministic_accepted is True
    assert info.sqlite_session_guardrail_windows_live_accepted is True


def test_step048_source_contract_is_explicit() -> None:
    gateway = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text()
    execution = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/service.py")).read_text()
    binding = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/runtime_binding.py")).read_text()
    assert "session_guardrail_mode" in gateway
    assert "definition.handoffs or definition.guardrails" in execution
    assert 'execution_path = "sqlite-session-native-guardrail-execution-v1"' in binding
    assert "SQLiteSessionGuardrailPolicyCatalog" in binding
    acceptance = (ROOT / "scripts/run_step048_acceptance.py").read_text()
    assert "workspace.finalize(payload)" in acceptance
