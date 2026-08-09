from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step020_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.governed_local_tool_approval_implemented is True
    assert info.governed_local_tool_runstate_encrypted is True
    assert info.governed_local_tool_process_restart_accepted is True
    assert info.governed_local_tool_generation_fencing_implemented is True
    assert info.governed_local_tool_approval_deterministic_accepted is True
    assert info.governed_local_tool_approval_windows_live_accepted is True
    assert info.governed_local_tool_approval_live_sdk_accepted is True
    assert info.operations_console_mutation_enabled is False
    assert info.direct_reference_import_forbidden is True


def test_step020_sdk_contract_and_specs_are_present() -> None:
    gateway = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/tool_approval/gateway.py")).read_text(encoding="utf-8")
    factories = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/function_tools/factories.py")).read_text(encoding="utf-8")
    assert "build_sdk_function_tool" in gateway
    assert 'needs_approval=runtime.approval_mode.value == "ALWAYS"' in factories
    assert "result.to_state().to_json(strict_context=True)" in gateway
    assert "RunState.from_json" in gateway
    assert "state.approve" in gateway
    assert "state.reject" in gateway
    assert (ROOT / "specs/agents/local-text-metrics-agent/definition.json").is_file()
    assert (ROOT / "specs/tools/local-text-metrics/policy.yaml").is_file()
    assert (ROOT / "docs/evidence/STEP020_ACCEPTANCE.json").is_file()


def test_step020_reference_is_not_imported() -> None:
    for path in (ROOT / "okcanvas_agent_runtime").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "from reference" not in text
        assert "import reference" not in text
        assert "reference/upstream" not in text
