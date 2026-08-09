from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step027_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.store_replenishment_multi_case_windows_live_accepted is True
    assert info.commerce_snapshot_failure_matrix_implemented is True
    assert info.commerce_snapshot_failure_matrix_case_count == 14
    assert info.commerce_snapshot_failure_matrix_deterministic_accepted is True
    assert info.commerce_snapshot_failure_matrix_windows_live_accepted is True


def test_step027_acceptance_evidence_is_complete() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP027_ACCEPTANCE.json").read_text(encoding="utf-8")
    )
    assert payload["state"] == "PASSED"
    assert payload["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
    assert payload["failure_case_count"] == 14
    assert len(payload["checks"]) == 24
    assert all(payload["checks"].values())
    assert payload["source"]["network_read_count"] == 9
    assert payload["source"]["redirect_target_reads"] == 0
    assert payload["source"]["transport_attempt_count"] == 1
    assert payload["source"]["write_count"] == 0
    assert payload["final_counts"] == {
        "submissions": 0,
        "tasks": 0,
        "runs": 0,
        "events": 0,
        "artifacts": 0,
        "evaluations": 0,
    }
    assert payload["artifact_count"] == 0
    assert payload["protected_payload_file_count"] == 0
    assert payload["gateway_call_count"] == 0
    cases = {item["case_id"]: item for item in payload["case_results"]}
    assert cases["transport-unavailable"]["retryable"] is True
    assert cases["auth-rejected"]["retryable"] is False
    assert cases["invalid-snapshot-key"]["http_status"] == 422
    assert cases["remote-origin"]["http_status"] == 503


def test_step027_windows_launcher_is_wired() -> None:
    launcher = (ROOT / "sh_run_step027_acceptance.cmd").read_text(encoding="utf-8")
    entrypoint = (ROOT / "scripts" / "windows_entrypoint.py").read_text(encoding="utf-8")
    assert "commerce-ingress-failure-matrix-acceptance" in launcher
    assert "run_step027_acceptance.py" in entrypoint
