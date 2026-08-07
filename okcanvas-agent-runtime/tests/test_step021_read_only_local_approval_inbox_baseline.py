from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step021_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.local_approval_inbox_api_implemented is True
    assert info.local_approval_inbox_console_implemented is True
    assert info.local_approval_inbox_read_only is True
    assert info.local_approval_inbox_deterministic_accepted is True
    assert info.local_approval_inbox_windows_live_accepted is True
    assert info.operations_console_mutation_enabled is False
    assert info.governed_local_tool_approval_live_sdk_accepted is True


def test_step021_artifacts_are_present() -> None:
    assert (ROOT / "scripts/run_step021_acceptance.py").is_file()
    assert (ROOT / "sh_run_step021_acceptance.cmd").is_file()
    assert (ROOT / "docs/evidence/STEP021_ACCEPTANCE.json").is_file()
    assert (ROOT / "docs/plans/STEP023_MINIMAL_LOCAL_APPROVAL_OPERATOR_CLI.md").is_file()
