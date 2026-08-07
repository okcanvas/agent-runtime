from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_step031_windows_live_acceptance_is_closed() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP031_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"] == "WINDOWS_LIVE_ACCEPTED"
    assert payload["state"] == "PASSED"
    assert payload["check_count"] == 19
    assert payload["all_checks_true"] is True
    assert payload["case_count"] == 5
    assert payload["max_inventory_unit_value"] == 45035996273704
    assert payload["case_contract"] == {
        "http_status": 502,
        "code": "COMMERCE_SNAPSHOT_INVALID",
        "retryable": False,
    }
    assert payload["source"] == {"read_count": 5, "write_count": 0}
    assert all(value == 0 for value in payload["final_counts"].values())
    assert payload["cleanup_state"] == "COMPLETED"


def test_step032_windows_live_acceptance_is_closed() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP032_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"] == "WINDOWS_LIVE_ACCEPTED"
    assert payload["state"] == "PASSED"
    assert payload["check_count"] == 19
    assert payload["all_checks_true"] is True
    assert payload["contract_count"] == 2
    assert payload["coding_valid"] == {"handler_present": False, "runner_calls": 1}
    assert payload["coding_invalid"]["error_code"] == "SDK_RUN_FAILED"
    assert payload["coding_invalid"]["recovered"] is False
    assert payload["replenishment_invalid"]["total_reorder_units"] == 19
    assert payload["replenishment_invalid"]["recovery_strategy"] == (
        "deterministic-invalid-final-output-fallback"
    )
    assert payload["no_tool_or_mcp_events"] is True
    assert payload["references_unchanged"] is True
    assert payload["cleanup_state"] == "COMPLETED"
