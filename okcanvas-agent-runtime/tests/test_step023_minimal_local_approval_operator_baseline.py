from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step023_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.local_approval_operator_cli_implemented is True
    assert info.local_approval_operator_loopback_only is True
    assert info.local_approval_operator_exact_confirmation_required is True
    assert info.local_approval_operator_deterministic_accepted is True
    assert info.local_approval_operator_windows_live_accepted is True
    assert info.approval_decision_api_exact_confirmation_required is True
    assert info.operations_console_mutation_enabled is False


def test_step023_artifacts_are_present() -> None:
    assert (legacy_source_contract(ROOT, "okcanvas_agent_runtime/approval_operator/client.py")).is_file()
    assert (ROOT / "scripts/run_step023_acceptance.py").is_file()
    assert (ROOT / "sh_run_step023_acceptance.cmd").is_file()
    assert (ROOT / "sh_approval_operator.cmd").is_file()
    assert (ROOT / "docs/plans/STEP023_MINIMAL_LOCAL_APPROVAL_OPERATOR_CLI.md").is_file()
    assert (ROOT / "docs/evidence/STEP023_ACCEPTANCE.json").is_file()
    assert (ROOT / "docs/evidence/STEP023_VALIDATION.txt").is_file()
