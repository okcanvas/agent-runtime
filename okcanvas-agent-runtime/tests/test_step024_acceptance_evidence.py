from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_step024_acceptance_evidence_is_complete() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP024_ACCEPTANCE.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["state"] == "PASSED"
    assert payload["live_sdk"] is False
    assert len(payload["checks"]) == 18
    assert all(payload["checks"].values())
    assert payload["result"]["status"] == "ACTION_REQUIRED"
    assert payload["result"]["total_reorder_units"] == 19
    assert payload["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
