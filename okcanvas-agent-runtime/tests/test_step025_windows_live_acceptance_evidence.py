from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_step025_windows_live_acceptance_is_closed() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP025_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["state"] == "PASSED"
    assert payload["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
    assert payload["artifact_count"] == 1
    assert payload["artifact_error"] is None
    assert payload["outcome_http_status"] == 200
    assert payload["outcome"]["status"] == "SUCCEEDED"
    assert len(payload["checks"]) == 21
    assert all(payload["checks"].values())
    assert payload["source_result"] == {
        "adapter_id": "controlled-commerce-http",
        "adapter_version": "1.0.0",
        "read_count": 1,
        "write_count": 0,
    }
    assert payload["result"]["total_reorder_units"] == 19
    assert [
        (item["sku"], item["reorder_units"])
        for item in payload["result"]["recommendations"]
    ] == [
        ("ergonomic-keyboard", 12),
        ("desk-lamp", 7),
        ("usb-c-dock", 0),
    ]
    assert not any(event.startswith("tool.") for event in payload["event_types"])
