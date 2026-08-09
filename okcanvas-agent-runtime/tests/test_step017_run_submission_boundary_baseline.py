from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import component_asset_root, read_component_source
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step017_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.run_submission_boundary_implemented is True
    assert info.run_submission_boundary_mode == "protected-payload-governed-read-only-and-approved-local-tool-execution"
    assert info.run_submission_idempotency_implemented is True
    assert info.run_submission_raw_payload_persisted is False
    assert info.run_submission_read_only_mode == "immediate-after-confirmation"
    assert info.run_submission_local_tool_mode == "approval-interrupted"
    assert info.run_submission_write_mcp_mode == "proposal-only"
    assert info.direct_run_api_default_enabled is False
    assert info.operations_console_mutation_enabled is False
    assert info.run_submission_boundary_deterministic_accepted is True
    assert info.run_submission_boundary_windows_live_accepted is True


def test_step017_console_still_has_no_mutation_request() -> None:
    assets = component_asset_root(ROOT, "operations_console.assets")
    script = (assets / "console.js").read_text(encoding="utf-8")
    html = (assets / "index.html").read_text(encoding="utf-8")
    assert "/v1/run-submission-policy" in script
    assert 'method:"POST"' not in script
    assert "Run Submission Boundary" in html
