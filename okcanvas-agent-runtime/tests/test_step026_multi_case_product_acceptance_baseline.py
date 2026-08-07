from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step026_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.store_replenishment_multi_case_acceptance_implemented is True
    assert info.store_replenishment_multi_case_valid_case_count == 4
    assert info.store_replenishment_invalid_source_case_accepted is True
    assert info.store_replenishment_multi_case_deterministic_accepted is True
    assert info.store_replenishment_multi_case_windows_live_accepted is True
    assert info.commerce_snapshot_ingress_windows_live_accepted is True


def test_step026_acceptance_evidence_is_complete() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP026_ACCEPTANCE.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["state"] == "PASSED"
    assert payload["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
    assert len(payload["checks"]) == 22
    assert all(payload["checks"].values())
    assert payload["valid_case_count"] == 4
    assert payload["source"]["read_count"] == 5
    assert payload["source"]["write_count"] == 0
    assert payload["artifact_count"] == 4
    assert payload["artifact_errors"] == []
    assert payload["invalid_case"]["http_status"] == 502
    assert payload["invalid_case"]["code"] == "COMMERCE_SNAPSHOT_INVALID"
    results = {item["case_id"]: item["result"] for item in payload["case_results"]}
    assert results["case001-shortage"]["total_reorder_units"] == 19
    assert results["case002-covered"]["status"] == "READY"
    assert results["case002-covered"]["total_reorder_units"] == 0
    assert [
        item["sku"] for item in results["case003-tie-ordering"]["recommendations"]
    ] == ["alpha-hub", "zeta-stand", "beta-mouse"]
    assert results["case004-single-shortage"]["total_reorder_units"] == 1


def test_step026_windows_launcher_is_wired() -> None:
    launcher = (ROOT / "sh_run_step026_acceptance.cmd").read_text(encoding="utf-8")
    entrypoint = (ROOT / "scripts" / "windows_entrypoint.py").read_text(encoding="utf-8")
    assert "commerce-multi-case-acceptance" in launcher
    assert "run_step026_acceptance.py" in entrypoint
