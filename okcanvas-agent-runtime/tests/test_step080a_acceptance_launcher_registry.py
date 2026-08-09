from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_acceptance_launcher_registry import validate

ROOT = Path(__file__).resolve().parents[1]


def test_acceptance_launcher_registry_is_complete_and_classified() -> None:
    result = validate()
    assert result["state"] == "PASSED"
    assert result["passed_checks"] == result["total_checks"] == 7
    assert result["script_count"] == len(list((ROOT / "scripts").glob("run_step*_acceptance.py")))
    assert result["launcher_count"] == len(list(ROOT.glob("sh_run_step*_acceptance.cmd")))
    assert result["record_count"] == result["script_count"] + result["launcher_count"]
    payload = json.loads((ROOT / "specs/acceptance/launcher-registry.json").read_text(encoding="utf-8"))
    assert result["current_record_count"] == len(payload["required_current_records"])


def test_registry_step080a_records_are_historical_after_step081() -> None:
    payload = json.loads(
        (ROOT / "specs/acceptance/launcher-registry.json").read_text(encoding="utf-8")
    )
    historical = {item["path"] for item in payload["records"] if item["classification"] == "HISTORICAL"}
    assert {
        "scripts/run_step080a_acceptance.py",
        "scripts/run_step080a_live_acceptance.py",
        "sh_run_step080a_acceptance.cmd",
        "sh_run_step080a_live_acceptance.cmd",
    }.issubset(historical)
    assert payload["current_step"] == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
