from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from okcanvas_agent_runtime.verticals.store_replenishment import (
    JSON_SAFE_INTEGER_MAX,
    MAX_DERIVED_ITEM_UNIT_VALUE,
    MAX_INVENTORY_UNIT_VALUE,
    MAX_REPLENISHMENT_ITEM_COUNT,
    StoreReplenishmentInput,
    build_store_replenishment_result,
)
from okcanvas_agent_runtime.verticals.commerce_snapshot_ingress import (
    CommerceSnapshotAdapterCatalog,
    CommerceSnapshotValidationError,
    ControlledCommerceHTTPAdapter,
)
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]
ENV = {
    "OKCANVAS_COMMERCE_SNAPSHOT_BASE_URL": "http://127.0.0.1:9325",
    "OKCANVAS_COMMERCE_SNAPSHOT_BEARER_TOKEN": "step031-test-token",
}


def _payload(**overrides: object) -> dict[str, object]:
    item = {
        "sku": "bounded-sku",
        "available_units": 1,
        "forecast_units": 2,
        "inbound_units": 0,
    }
    item.update(overrides.pop("item", {}))
    payload: dict[str, object] = {
        "snapshot_id": "bounded-snapshot",
        "safety_stock_units": 1,
        "items": [item],
    }
    payload.update(overrides)
    return payload


def test_step031_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.commerce_snapshot_non_empty_inventory_windows_live_accepted is True
    assert info.step030_windows_venv_launcher_live_accepted is True
    assert info.commerce_snapshot_bounded_quantities_implemented is True
    assert info.commerce_snapshot_max_inventory_unit_value == MAX_INVENTORY_UNIT_VALUE
    assert info.commerce_snapshot_json_safe_derived_totals_enforced is True
    assert info.commerce_snapshot_overlong_integer_literal_rejected is True
    assert info.commerce_snapshot_bounded_quantities_deterministic_accepted is True
    assert info.commerce_snapshot_bounded_quantities_windows_live_accepted is True


def test_quantity_bound_is_derived_from_json_safe_total_contract() -> None:
    assert JSON_SAFE_INTEGER_MAX == (1 << 53) - 1
    assert MAX_REPLENISHMENT_ITEM_COUNT == 100
    assert MAX_INVENTORY_UNIT_VALUE == JSON_SAFE_INTEGER_MAX // 200
    assert MAX_DERIVED_ITEM_UNIT_VALUE == 2 * MAX_INVENTORY_UNIT_VALUE
    assert MAX_REPLENISHMENT_ITEM_COUNT * MAX_DERIVED_ITEM_UNIT_VALUE <= JSON_SAFE_INTEGER_MAX


@pytest.mark.parametrize(
    ("field", "payload"),
    [
        (
            "safety_stock_units",
            _payload(safety_stock_units=MAX_INVENTORY_UNIT_VALUE + 1),
        ),
        (
            "available_units",
            _payload(item={"available_units": MAX_INVENTORY_UNIT_VALUE + 1}),
        ),
        (
            "forecast_units",
            _payload(item={"forecast_units": MAX_INVENTORY_UNIT_VALUE + 1}),
        ),
        (
            "inbound_units",
            _payload(item={"inbound_units": MAX_INVENTORY_UNIT_VALUE + 1}),
        ),
    ],
)
def test_input_rejects_every_quantity_above_product_bound(
    field: str, payload: dict[str, object]
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        StoreReplenishmentInput.model_validate(payload)
    assert any(error["type"] == "less_than_equal" for error in exc_info.value.errors())
    assert field in str(exc_info.value)


def test_maximum_valid_matrix_keeps_derived_total_json_safe() -> None:
    payload = {
        "snapshot_id": "maximum-valid-matrix",
        "safety_stock_units": MAX_INVENTORY_UNIT_VALUE,
        "items": [
            {
                "sku": f"sku-{index:03d}",
                "available_units": 0,
                "forecast_units": MAX_INVENTORY_UNIT_VALUE,
                "inbound_units": 0,
            }
            for index in range(MAX_REPLENISHMENT_ITEM_COUNT)
        ],
    }
    validated = StoreReplenishmentInput.model_validate(payload)
    assert len(validated.items) == 100
    result = build_store_replenishment_result(json.dumps(payload))
    assert result.total_reorder_units == 100 * MAX_DERIVED_ITEM_UNIT_VALUE
    assert result.total_reorder_units <= JSON_SAFE_INTEGER_MAX
    assert all(item.reorder_units == MAX_DERIVED_ITEM_UNIT_VALUE for item in result.recommendations)


def test_adapter_rejects_overlong_integer_literal_as_safe_validation_error() -> None:
    huge = "9" * 5000
    body = (
        '{"snapshot_id":"bounded-snapshot","safety_stock_units":1,'
        '"items":[{"sku":"bounded-sku","available_units":1,'
        f'"forecast_units":{huge},"inbound_units":0}}]'
    ).encode("utf-8")

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=body,
        )

    adapter = ControlledCommerceHTTPAdapter(
        CommerceSnapshotAdapterCatalog(ROOT).resolve("controlled-commerce-http"),
        environment=ENV,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(CommerceSnapshotValidationError):
        asyncio.run(adapter.acquire("bounded-snapshot"))


def test_step031_acceptance_evidence_is_complete() -> None:
    payload = json.loads(
        (ROOT / "docs" / "evidence" / "STEP031_ACCEPTANCE.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["state"] == "PASSED"
    assert payload["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
    assert len(payload["checks"]) == 19
    assert all(payload["checks"].values())
    assert payload["max_inventory_unit_value"] == MAX_INVENTORY_UNIT_VALUE
    assert payload["case_count"] == 5
    assert all(item["http_status"] == 502 for item in payload["case_results"])
    assert all(item["code"] == "COMMERCE_SNAPSHOT_INVALID" for item in payload["case_results"])
    assert all(item["retryable"] is False for item in payload["case_results"])
    assert payload["source"]["read_count"] == 5
    assert payload["source"]["write_count"] == 0
    assert all(value == 0 for value in payload["final_counts"].values())
    assert payload["artifact_count"] == 0
    assert payload["protected_payload_file_count"] == 0
    assert payload["gateway_call_count"] == 0


def test_step031_windows_launcher_is_wired() -> None:
    launcher = (ROOT / "sh_run_step031_acceptance.cmd").read_text(encoding="utf-8")
    entrypoint = (ROOT / "scripts" / "windows_entrypoint.py").read_text(encoding="utf-8")
    assert 'if not exist ".venv\\Scripts\\python.exe"' in launcher
    assert (
        '".venv\\Scripts\\python.exe" scripts\\windows_entrypoint.py '
        "commerce-snapshot-bounded-quantities-acceptance %*"
    ) in launcher
    assert "run_step031_acceptance.py" in entrypoint
