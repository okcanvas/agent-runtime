from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step028_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.commerce_snapshot_failure_matrix_windows_live_accepted is True
    assert info.commerce_snapshot_response_identity_bound is True
    assert info.commerce_snapshot_identity_mismatch_code == "COMMERCE_SNAPSHOT_IDENTITY_MISMATCH"
    assert info.commerce_snapshot_identity_consistency_deterministic_accepted is True
    assert info.commerce_snapshot_identity_consistency_windows_live_accepted is True


def test_step028_acceptance_evidence_is_complete() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP028_ACCEPTANCE.json").read_text(encoding="utf-8")
    )
    assert payload["state"] == "PASSED"
    assert payload["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
    assert len(payload["checks"]) == 15
    assert all(payload["checks"].values())
    assert payload["response"] == {
        "http_status": 502,
        "code": "COMMERCE_SNAPSHOT_IDENTITY_MISMATCH",
        "retryable": False,
        "message": "Commerce snapshot identity did not match the requested snapshot key",
    }
    assert payload["source"]["read_count"] == 1
    assert payload["source"]["write_count"] == 0
    assert payload["source"]["requested_paths"] == ["step028-requested-snapshot"]
    assert all(value == 0 for value in payload["final_counts"].values())
    assert payload["artifact_count"] == 0
    assert payload["protected_payload_file_count"] == 0
    assert payload["gateway_call_count"] == 0


def test_step028_windows_launcher_is_wired() -> None:
    launcher = (ROOT / "sh_run_step028_acceptance.cmd").read_text(encoding="utf-8")
    entrypoint = (ROOT / "scripts" / "windows_entrypoint.py").read_text(encoding="utf-8")
    assert "commerce-snapshot-identity-acceptance" in launcher
    assert "run_step028_acceptance.py" in entrypoint
