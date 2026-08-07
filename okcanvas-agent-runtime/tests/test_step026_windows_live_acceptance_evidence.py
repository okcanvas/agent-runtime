from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_step026_windows_live_acceptance_is_closed() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP026_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["state"] == "PASSED"
    assert payload["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
    assert payload["valid_case_count"] == 4
    assert payload["artifact_count"] == 4
    assert payload["artifact_errors"] == []
    assert len(payload["checks"]) == 22
    assert all(payload["checks"].values())
    assert payload["source_result"]["read_count"] == 5
    assert payload["source_result"]["write_count"] == 0
    assert payload["invalid_case"]["code"] == "COMMERCE_SNAPSHOT_INVALID"
    assert payload["invalid_case"]["counts_before"] == payload["invalid_case"]["counts_after"]
    results = {item["case_id"]: item for item in payload["case_results"]}
    assert [results[key]["total_reorder_units"] for key in (
        "case001-shortage", "case002-covered", "case003-tie-ordering", "case004-single-shortage"
    )] == [19, 0, 10, 1]
    assert results["case002-covered"]["status"] == "READY"
    assert [item[0] for item in results["case003-tie-ordering"]["recommendations"]] == [
        "alpha-hub", "zeta-stand", "beta-mouse"
    ]
