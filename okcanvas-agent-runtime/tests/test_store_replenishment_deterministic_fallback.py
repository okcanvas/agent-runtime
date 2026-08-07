from __future__ import annotations

import json

from okcanvas_agent_runtime.verticals.store_replenishment import build_store_replenishment_result


def test_deterministic_replenishment_fallback_calculates_exact_result() -> None:
    result = build_store_replenishment_result(
        json.dumps(
            {
                "snapshot_id": "case001-shortage",
                "safety_stock_units": 5,
                "items": [
                    {
                        "sku": "desk-lamp",
                        "available_units": 12,
                        "forecast_units": 18,
                        "inbound_units": 4,
                    },
                    {
                        "sku": "ergonomic-keyboard",
                        "available_units": 7,
                        "forecast_units": 16,
                        "inbound_units": 2,
                    },
                    {
                        "sku": "usb-c-dock",
                        "available_units": 22,
                        "forecast_units": 14,
                        "inbound_units": 0,
                    },
                ],
            },
            separators=(",", ":"),
        )
    )
    assert result.status.value == "ACTION_REQUIRED"
    assert result.total_reorder_units == 19
    assert [(item.sku, item.reorder_units) for item in result.recommendations] == [
        ("ergonomic-keyboard", 12),
        ("desk-lamp", 7),
        ("usb-c-dock", 0),
    ]


def test_deterministic_replenishment_fallback_returns_insufficient_data() -> None:
    result = build_store_replenishment_result(
        '{"snapshot_id":"bad","safety_stock_units":5,"items":[{"sku":"dup","available_units":1,"forecast_units":2,"inbound_units":0},{"sku":"dup","available_units":1,"forecast_units":2,"inbound_units":0}]}'
    )
    assert result.status.value == "INSUFFICIENT_DATA"
    assert result.snapshot_id == "bad"
    assert result.recommendations == []
    assert result.unverified


def test_deterministic_replenishment_fallback_rejects_non_json_without_leaking_input() -> None:
    result = build_store_replenishment_result("not-json SECRET_SENTINEL")
    assert result.status.value == "INSUFFICIENT_DATA"
    assert result.snapshot_id == "unverified-input"
    assert "SECRET_SENTINEL" not in result.model_dump_json()
