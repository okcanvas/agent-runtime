from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from okcanvas_agent_runtime.verticals.store_replenishment import StoreReplenishmentInput, build_store_replenishment_result
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def _empty_payload() -> dict[str, object]:
    return {
        "snapshot_id": "case006-invalid-empty-items",
        "safety_stock_units": 2,
        "items": [],
    }


def test_step030_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.commerce_snapshot_strict_scalar_types_windows_live_accepted is True
    assert info.commerce_snapshot_non_empty_inventory_implemented is True
    assert info.commerce_snapshot_empty_inventory_rejected is True
    assert info.commerce_snapshot_non_empty_inventory_deterministic_accepted is True
    assert info.commerce_snapshot_non_empty_inventory_windows_live_accepted is True
    assert info.windows_project_venv_launcher_enforced is True
    assert info.step030_windows_venv_launcher_fix_implemented is True
    assert info.step030_windows_venv_launcher_deterministic_accepted is True
    assert info.step030_windows_venv_launcher_live_accepted is True


def test_store_replenishment_input_rejects_empty_inventory_rows() -> None:
    with pytest.raises(ValidationError):
        StoreReplenishmentInput.model_validate(_empty_payload())


def test_deterministic_recovery_does_not_report_false_ready_for_empty_inventory() -> None:
    result = build_store_replenishment_result(json.dumps(_empty_payload()))
    assert result.status.value == "INSUFFICIENT_DATA"
    assert result.reviewed_skus == 0
    assert result.total_reorder_units == 0
    assert result.recommendations == []
    assert any(item.startswith("items:") for item in result.unverified)


def test_step030_invalid_fixture_is_canonical() -> None:
    fixture = json.loads(
        (
            ROOT
            / "specs"
            / "business-cases"
            / "store-replenishment-review"
            / "case006-invalid-empty-items"
            / "input.json"
        ).read_text(encoding="utf-8")
    )
    assert fixture == _empty_payload()


def test_step030_acceptance_evidence_is_complete() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP030_ACCEPTANCE.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["state"] == "PASSED"
    assert payload["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
    assert len(payload["checks"]) == 15
    assert all(payload["checks"].values())
    assert payload["response"]["http_status"] == 502
    assert payload["response"]["code"] == "COMMERCE_SNAPSHOT_INVALID"
    assert payload["response"]["retryable"] is False
    assert payload["source"]["read_count"] == 1
    assert payload["source"]["write_count"] == 0
    assert all(value == 0 for value in payload["final_counts"].values())
    assert payload["artifact_count"] == 0
    assert payload["protected_payload_file_count"] == 0
    assert payload["gateway_call_count"] == 0


def test_step030_windows_launcher_is_wired() -> None:
    launcher = (ROOT / "sh_run_step030_acceptance.cmd").read_text(encoding="utf-8")
    entrypoint = (ROOT / "scripts" / "windows_entrypoint.py").read_text(encoding="utf-8")
    assert 'if not exist ".venv\\Scripts\\python.exe"' in launcher
    assert '".venv\\Scripts\\python.exe" scripts\\windows_entrypoint.py commerce-snapshot-non-empty-acceptance %*' in launcher
    assert "\npython scripts\\windows_entrypoint.py" not in launcher.replace("\r\n", "\n")
    assert "run_step030_acceptance.py" in entrypoint
