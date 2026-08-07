from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from okcanvas_agent_runtime.core.contracts import ReplenishmentAction, ReplenishmentReviewStatus, ReplenishmentRisk, StoreReplenishmentRecommendation, StoreReplenishmentReviewResult
from okcanvas_agent_runtime.core.replenishment_limits import JSON_SAFE_INTEGER_MAX, MAX_DERIVED_ITEM_UNIT_VALUE, MAX_INVENTORY_UNIT_VALUE, MAX_REPLENISHMENT_ITEM_COUNT


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class StoreReplenishmentInputItem(_StrictModel):
    sku: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
    available_units: int = Field(ge=0, le=MAX_INVENTORY_UNIT_VALUE)
    forecast_units: int = Field(ge=0, le=MAX_INVENTORY_UNIT_VALUE)
    inbound_units: int = Field(ge=0, le=MAX_INVENTORY_UNIT_VALUE)


class StoreReplenishmentInput(_StrictModel):
    snapshot_id: str = Field(min_length=1, max_length=200)
    safety_stock_units: int = Field(ge=0, le=MAX_INVENTORY_UNIT_VALUE)
    items: list[StoreReplenishmentInputItem] = Field(
        min_length=1, max_length=MAX_REPLENISHMENT_ITEM_COUNT
    )

    @model_validator(mode="after")
    def validate_unique_skus(self) -> "StoreReplenishmentInput":
        if len({item.sku for item in self.items}) != len(self.items):
            raise ValueError("input SKUs must be unique")
        return self


def _safe_snapshot_id(payload: Any) -> str:
    if isinstance(payload, dict):
        candidate = payload.get("snapshot_id")
        if isinstance(candidate, str) and 1 <= len(candidate.strip()) <= 200:
            return candidate.strip()
    return "unverified-input"


def _validation_messages(exc: ValidationError) -> list[str]:
    messages: list[str] = []
    for error in exc.errors(include_url=False):
        location = ".".join(str(part) for part in error.get("loc", ())) or "input"
        error_type = str(error.get("type", "validation_error"))
        messages.append(f"{location}: {error_type}")
        if len(messages) >= 20:
            break
    return messages or ["input: validation_error"]


def build_store_replenishment_result(request: str) -> StoreReplenishmentReviewResult:
    """Build the authoritative replenishment result from the supplied snapshot.

    Exact arithmetic and ordering are product-owned deterministic rules. This function is used as
    the SDK invalid-final-output fallback, so a malformed model response cannot change inventory
    math or silently create a partial Artifact.
    """

    try:
        payload = json.loads(request)
    except json.JSONDecodeError:
        return StoreReplenishmentReviewResult(
            status=ReplenishmentReviewStatus.INSUFFICIENT_DATA,
            snapshot_id="unverified-input",
            summary="The replenishment snapshot is not valid JSON.",
            reviewed_skus=0,
            total_reorder_units=0,
            recommendations=[],
            unverified=["input: invalid_json"],
        )

    try:
        snapshot = StoreReplenishmentInput.model_validate(payload)
    except ValidationError as exc:
        return StoreReplenishmentReviewResult(
            status=ReplenishmentReviewStatus.INSUFFICIENT_DATA,
            snapshot_id=_safe_snapshot_id(payload),
            summary="The replenishment snapshot is incomplete or invalid.",
            reviewed_skus=0,
            total_reorder_units=0,
            recommendations=[],
            unverified=_validation_messages(exc),
        )

    recommendations: list[StoreReplenishmentRecommendation] = []
    for item in snapshot.items:
        projected_units = item.available_units + item.inbound_units - item.forecast_units
        reorder_units = max(
            item.forecast_units
            + snapshot.safety_stock_units
            - item.available_units
            - item.inbound_units,
            0,
        )
        if reorder_units > 0:
            action = ReplenishmentAction.REORDER
            risk = ReplenishmentRisk.SHORTAGE
            reason = (
                f"Available and inbound units are {reorder_units} units below forecast demand "
                "plus safety stock."
            )
        else:
            action = ReplenishmentAction.NO_ACTION
            risk = ReplenishmentRisk.COVERED
            reason = "Available and inbound units cover forecast demand and the safety stock target."
        recommendations.append(
            StoreReplenishmentRecommendation(
                sku=item.sku,
                available_units=item.available_units,
                forecast_units=item.forecast_units,
                inbound_units=item.inbound_units,
                safety_stock_units=snapshot.safety_stock_units,
                projected_units=projected_units,
                reorder_units=reorder_units,
                action=action,
                risk=risk,
                reason=reason,
            )
        )

    recommendations.sort(key=lambda item: (-item.reorder_units, item.sku))
    total_reorder_units = sum(item.reorder_units for item in recommendations)
    reorder_skus = sum(1 for item in recommendations if item.reorder_units > 0)
    if reorder_skus == 0:
        summary = "No SKUs require replenishment for the supplied forecast and safety stock target."
    elif reorder_skus == 1:
        summary = "One SKU requires replenishment for the supplied forecast and safety stock target."
    else:
        summary = (
            f"{reorder_skus} SKUs require replenishment for the supplied forecast and safety "
            "stock target."
        )
    return StoreReplenishmentReviewResult(
        status=(
            ReplenishmentReviewStatus.ACTION_REQUIRED
            if total_reorder_units > 0
            else ReplenishmentReviewStatus.READY
        ),
        snapshot_id=snapshot.snapshot_id,
        summary=summary,
        reviewed_skus=len(recommendations),
        total_reorder_units=total_reorder_units,
        recommendations=recommendations,
        unverified=[],
    )
