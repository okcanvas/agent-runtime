from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step022_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.live_acceptance_closure_harness_implemented is True
    assert info.live_acceptance_closure_deterministic_accepted is True
    assert info.live_acceptance_closure_windows_accepted is True
    assert info.governed_local_tool_approval_live_sdk_accepted is True
    assert info.local_approval_inbox_windows_live_accepted is True
    assert info.operations_console_mutation_enabled is False


def test_step022_artifacts_are_present() -> None:
    assert (ROOT / "scripts/run_step022_acceptance.py").is_file()
    assert (ROOT / "sh_run_step022_acceptance.cmd").is_file()
    assert (ROOT / "sh_run_step022_live_closure.cmd").is_file()
    assert (ROOT / "docs/plans/STEP023_MINIMAL_LOCAL_APPROVAL_OPERATOR_CLI.md").is_file()
    assert (ROOT / "docs/evidence/STEP022_ACCEPTANCE.json").is_file()
    assert (ROOT / "docs/evidence/STEP022_VALIDATION.txt").is_file()
