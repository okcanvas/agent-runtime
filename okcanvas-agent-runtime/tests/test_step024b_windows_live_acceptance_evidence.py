from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_step024b_windows_live_acceptance_is_closed() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP024B_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["state"] == "PASSED"
    assert payload["live_sdk"] is True
    assert payload["output_recovered"] is True
    assert payload["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
    assert payload["artifact_count"] == 1
    assert payload["artifact_error"] is None
    assert payload["outcome_http_status"] == 200
    assert payload["outcome"]["status"] == "SUCCEEDED"
    assert len(payload["checks"]) == 18
    assert all(payload["checks"].values())
    assert payload["result"]["total_reorder_units"] == 19
    assert [
        (item["sku"], item["reorder_units"])
        for item in payload["result"]["recommendations"]
    ] == [
        ("ergonomic-keyboard", 12),
        ("desk-lamp", 7),
        ("usb-c-dock", 0),
    ]
    assert "agent.output.recovered" in payload["event_types"]
    assert not any(event.startswith("tool.") for event in payload["event_types"])
