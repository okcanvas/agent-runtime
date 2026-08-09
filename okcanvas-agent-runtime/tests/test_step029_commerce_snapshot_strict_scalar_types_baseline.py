from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from okcanvas_agent_runtime.verticals.store_replenishment import StoreReplenishmentInput
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step029_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.commerce_snapshot_identity_consistency_windows_live_accepted is True
    assert info.commerce_snapshot_strict_scalar_types_implemented is True
    assert info.commerce_snapshot_scalar_coercion_rejected is True
    assert info.commerce_snapshot_strict_scalar_type_case_count == 4
    assert info.commerce_snapshot_strict_scalar_types_deterministic_accepted is True
    assert info.commerce_snapshot_strict_scalar_types_windows_live_accepted is True


@pytest.mark.parametrize(
    "payload",
    [
        {"snapshot_id": "a", "safety_stock_units": "2", "items": []},
        {
            "snapshot_id": "a",
            "safety_stock_units": 2,
            "items": [
                {"sku": "a", "available_units": True, "forecast_units": 1, "inbound_units": 0}
            ],
        },
        {
            "snapshot_id": "a",
            "safety_stock_units": 2,
            "items": [
                {"sku": "a", "available_units": 1, "forecast_units": 1.0, "inbound_units": 0}
            ],
        },
        {
            "snapshot_id": "a",
            "safety_stock_units": 2,
            "items": [
                {"sku": "a", "available_units": 1, "forecast_units": 1, "inbound_units": "0"}
            ],
        },
    ],
)
def test_store_replenishment_input_rejects_coercible_integer_values(payload) -> None:
    with pytest.raises(ValidationError):
        StoreReplenishmentInput.model_validate(payload)


def test_step029_acceptance_evidence_is_complete() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP029_ACCEPTANCE.json").read_text(encoding="utf-8")
    )
    assert payload["state"] == "PASSED"
    assert payload["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
    assert payload["case_count"] == 4
    assert len(payload["checks"]) == 18
    assert all(payload["checks"].values())
    assert all(item["http_status"] == 502 for item in payload["case_results"])
    assert all(item["code"] == "COMMERCE_SNAPSHOT_INVALID" for item in payload["case_results"])
    assert all(item["retryable"] is False for item in payload["case_results"])
    assert payload["source"]["read_count"] == 4
    assert payload["source"]["write_count"] == 0
    assert all(value == 0 for value in payload["final_counts"].values())
    assert payload["artifact_count"] == 0
    assert payload["protected_payload_file_count"] == 0
    assert payload["gateway_call_count"] == 0


def test_step029_windows_launcher_is_wired() -> None:
    launcher = (ROOT / "sh_run_step029_acceptance.cmd").read_text(encoding="utf-8")
    entrypoint = (ROOT / "scripts" / "windows_entrypoint.py").read_text(encoding="utf-8")
    assert "commerce-snapshot-strict-types-acceptance" in launcher
    assert "run_step029_acceptance.py" in entrypoint
