from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_step028_windows_live_acceptance_is_closed() -> None:
    envelope = json.loads(
        (ROOT / "docs" / "evidence" / "STEP028_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert envelope["status"] == "WINDOWS_LIVE_ACCEPTED"
    payload = envelope["result"]
    assert payload["state"] == "PASSED"
    assert payload["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
    assert len(payload["checks"]) == 15
    assert all(payload["checks"].values())
    assert payload["response"] == {
        "code": "COMMERCE_SNAPSHOT_IDENTITY_MISMATCH",
        "http_status": 502,
        "message": "Commerce snapshot identity did not match the requested snapshot key",
        "retryable": False,
    }
    assert payload["source"] == {
        "read_count": 1,
        "requested_paths": ["step028-requested-snapshot"],
        "write_count": 0,
    }
    assert all(value == 0 for value in payload["final_counts"].values())
    assert payload["artifact_count"] == 0
    assert payload["protected_payload_file_count"] == 0
    assert payload["gateway_call_count"] == 0
