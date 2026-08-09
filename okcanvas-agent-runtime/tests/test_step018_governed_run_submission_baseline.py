from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import component_asset_root, read_component_source
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step018_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.run_submission_boundary_mode == "protected-payload-governed-read-only-and-approved-local-tool-execution"
    assert info.protected_payload_store_implemented is True
    assert info.protected_payload_backend == "aes-256-gcm-encrypted-files"
    assert info.protected_payload_key_external_only is True
    assert info.protected_payload_integrity_verified is True
    assert info.separate_run_submitter_authority_implemented is True
    assert info.governed_read_only_submission_implemented is True
    assert info.governed_read_only_task_run_atomic_binding is True
    assert info.governed_read_only_confirmation_idempotent is True
    assert info.governed_read_only_submission_deterministic_accepted is True
    assert info.governed_read_only_submission_windows_live_accepted is False
    assert info.governed_execution_claim_restart_recovery_implemented is True
    assert info.run_submission_raw_payload_persisted is False
    assert info.run_submission_local_tool_mode == "approval-interrupted"
    assert info.run_submission_write_mcp_mode == "proposal-only"
    assert info.direct_run_api_default_enabled is False
    assert info.operations_console_mutation_enabled is False


def test_step018_has_governed_submission_api_but_console_stays_get_only() -> None:
    app_source = read_component_source(ROOT, "control_api.app")
    console_source = (
        component_asset_root(ROOT, "operations_console.assets") / "console.js"
    ).read_text(encoding="utf-8")
    assert "/v1/run-submissions/preflight" in app_source
    assert "/v1/run-submissions/{submission_id}/confirm" in app_source
    assert 'method:"POST"' not in console_source
    assert "/reference" not in app_source
