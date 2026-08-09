from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import component_asset_root
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step037_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.interactive_agent_runner_implemented is True
    assert info.interactive_agent_runner_mode == "separate-governed-run-submitter"
    assert info.interactive_agent_runner_approval_decision_enabled is False
    assert info.run_artifact_read_api_implemented is True
    assert info.interactive_agent_runner_deterministic_accepted is True
    assert info.interactive_agent_runner_windows_live_accepted is True
    assert (component_asset_root(ROOT, "interactive_runner.assets") / "index.html").is_file()
    assert (ROOT / "scripts" / "run_step037_acceptance.py").is_file()
    assert (ROOT / "sh_run_step037_acceptance.cmd").is_file()
