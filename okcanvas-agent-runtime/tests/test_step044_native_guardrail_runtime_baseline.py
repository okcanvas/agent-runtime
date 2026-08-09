from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step044_assets_exist() -> None:
    required = [
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/guardrails/models.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/guardrails/catalog.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/guardrails/runtime.py"),
        ROOT / "specs/guardrails/block-input-marker/definition.json",
        ROOT / "specs/guardrails/block-output-marker/definition.json",
        ROOT / "specs/guardrails/deny-local-text-tool-input/definition.json",
        ROOT / "specs/guardrails/deny-local-text-tool-output/definition.json",
        ROOT / "specs/agents/guardrail-language-agent/definition.json",
        ROOT / "specs/agents/guardrail-tool-input-agent/definition.json",
        ROOT / "specs/agents/guardrail-tool-output-agent/definition.json",
        ROOT / "specs/evaluations/native-guardrail-v1/case.json",
        ROOT / "scripts/run_step044_acceptance.py",
        ROOT / "sh_run_step044_acceptance.cmd",
        ROOT / "docs/plans/STEP045_INTEGRATED_WALKING_SKELETON_ACCEPTANCE.md",
        ROOT / "docs/reference/STEP044_NATIVE_GUARDRAIL_RUNTIME_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP043_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
        ROOT / "docs/evidence/STEP044_ACCEPTANCE.json",
        ROOT / "docs/evidence/STEP044_VALIDATION.txt",
    ]
    assert all(path.is_file() for path in required)


def test_step044_runtime_info_is_current() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.sqlite_session_windows_live_accepted is True
    assert info.native_guardrail_runtime_implemented is True
    assert info.native_guardrail_input_supported is True
    assert info.native_guardrail_output_supported is True
    assert info.native_guardrail_tool_input_supported is True
    assert info.native_guardrail_tool_output_supported is True
    assert info.native_guardrail_raw_content_persisted is False
    assert info.native_guardrail_rejected_artifact_created is False
    assert info.native_guardrail_deterministic_accepted is True
    assert info.native_guardrail_windows_live_accepted is True


def test_step044_contract_is_explicit_in_runtime_code() -> None:
    gateway = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text(encoding="utf-8")
    service = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/service.py")).read_text(encoding="utf-8")
    binding = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/runtime_binding.py")).read_text(encoding="utf-8")
    assert "InputGuardrailTripwireTriggered" in gateway
    assert "OutputGuardrailTripwireTriggered" in gateway
    assert "ToolInputGuardrailTripwireTriggered" in gateway
    assert "ToolOutputGuardrailTripwireTriggered" in gateway
    assert '"guardrail.tripped"' in gateway
    assert '"guarded_content_persisted": False' in gateway
    assert "native-guardrail-execution-v1" in service
    assert "guardrail_runtime_sha256" in binding
