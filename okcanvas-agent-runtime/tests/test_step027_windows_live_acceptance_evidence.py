from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_step027_windows_live_acceptance_is_closed() -> None:
    envelope = json.loads(
        (ROOT / "docs" / "evidence" / "STEP027_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert envelope["status"] == "WINDOWS_LIVE_ACCEPTED"
    payload = envelope["result"]
    assert payload["state"] == "PASSED"
    assert payload["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
    assert payload["failure_case_count"] == 14
    assert len(payload["checks"]) == 24
    assert all(payload["checks"].values())
    assert payload["source"] == {
        "adapter_id": "controlled-commerce-http",
        "adapter_version": "1.0.0",
        "network_read_count": 9,
        "network_reads_by_key": {
            "auth-rejected": 1,
            "empty-body": 1,
            "invalid-utf8": 1,
            "malformed-json": 1,
            "oversized": 1,
            "redirect": 1,
            "too-many-items": 1,
            "upstream-503": 1,
            "wrong-content-type": 1,
        },
        "redirect_target_reads": 0,
        "transport_attempt_count": 1,
        "write_count": 0,
    }
    assert payload["final_counts"] == {
        "artifacts": 0,
        "evaluations": 0,
        "events": 0,
        "runs": 0,
        "submissions": 0,
        "tasks": 0,
    }
    assert payload["artifact_count"] == 0
    assert payload["protected_payload_file_count"] == 0
    assert payload["gateway_call_count"] == 0
