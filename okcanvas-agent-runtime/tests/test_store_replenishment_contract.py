from __future__ import annotations

import pytest
from pydantic import ValidationError

from okcanvas_agent_runtime.core.contracts import StoreReplenishmentReviewResult


def _valid() -> dict:
    return {
        "schema_version": "okcanvas-store-replenishment-review-v1",
        "status": "ACTION_REQUIRED",
        "snapshot_id": "case001-shortage",
        "summary": "Two SKUs require replenishment.",
        "reviewed_skus": 3,
        "total_reorder_units": 19,
        "recommendations": [
            {
                "sku": "ergonomic-keyboard",
                "available_units": 7,
                "forecast_units": 16,
                "inbound_units": 2,
                "safety_stock_units": 5,
                "projected_units": -7,
                "reorder_units": 12,
                "action": "REORDER",
                "risk": "SHORTAGE",
                "reason": "Short by twelve units.",
            },
            {
                "sku": "desk-lamp",
                "available_units": 12,
                "forecast_units": 18,
                "inbound_units": 4,
                "safety_stock_units": 5,
                "projected_units": -2,
                "reorder_units": 7,
                "action": "REORDER",
                "risk": "SHORTAGE",
                "reason": "Short by seven units.",
            },
            {
                "sku": "usb-c-dock",
                "available_units": 22,
                "forecast_units": 14,
                "inbound_units": 0,
                "safety_stock_units": 5,
                "projected_units": 8,
                "reorder_units": 0,
                "action": "NO_ACTION",
                "risk": "COVERED",
                "reason": "Inventory covers demand and safety stock.",
            },
        ],
        "unverified": [],
    }


def test_business_contract_enforces_replenishment_equations() -> None:
    result = StoreReplenishmentReviewResult.model_validate(_valid())
    assert result.total_reorder_units == 19
    assert [item.sku for item in result.recommendations] == [
        "ergonomic-keyboard",
        "desk-lamp",
        "usb-c-dock",
    ]


def test_business_contract_rejects_wrong_reorder_math() -> None:
    payload = _valid()
    payload["recommendations"][0]["reorder_units"] = 11
    with pytest.raises(ValidationError):
        StoreReplenishmentReviewResult.model_validate(payload)


def test_business_contract_rejects_unsorted_recommendations() -> None:
    payload = _valid()
    payload["recommendations"][0], payload["recommendations"][1] = (
        payload["recommendations"][1],
        payload["recommendations"][0],
    )
    with pytest.raises(ValidationError):
        StoreReplenishmentReviewResult.model_validate(payload)


def test_insufficient_data_requires_unverified_reason() -> None:
    with pytest.raises(ValidationError):
        StoreReplenishmentReviewResult.model_validate(
            {
                "schema_version": "okcanvas-store-replenishment-review-v1",
                "status": "INSUFFICIENT_DATA",
                "snapshot_id": "bad-input",
                "summary": "Input is incomplete.",
                "reviewed_skus": 0,
                "total_reorder_units": 0,
                "recommendations": [],
                "unverified": [],
            }
        )
