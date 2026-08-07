# STEP031 — Bounded Commerce Snapshot Quantities

STEP031 prevents externally supplied inventory numbers from exceeding a product-owned JSON-safe calculation range.

## Code-proven defect

Before STEP031, the four replenishment quantity fields had only `ge=0`. Direct execution proved that a 1,000-digit `forecast_units` value passed `StoreReplenishmentInput` validation. The deterministic result builder then failed while constructing `StoreReplenishmentRecommendation` because the decimal value made `reason` exceed its 1,000-character output limit.

The ingress parser also relied on Python's process-level integer-string limit. A sufficiently long integer literal could raise a plain `ValueError` outside the previously handled JSON exceptions.

## Product-owned bound

Product results are JSON and may be consumed by browser and cross-language clients. All derived integers must therefore remain within the exact JSON integer range:

```text
JSON_SAFE_INTEGER_MAX = 2^53 - 1
MAX_ITEMS = 100
MAX_INVENTORY_UNIT_VALUE = floor(JSON_SAFE_INTEGER_MAX / (2 × MAX_ITEMS))
                         = 45,035,996,273,704
```

The factor of two covers the worst per-SKU replenishment equation:

```text
forecast_units + safety_stock_units
```

With 100 items, the maximum possible total remains at or below `2^53 - 1`.

## Enforced contract

The following input fields are strict JSON integers in the inclusive range `0..45,035,996,273,704`:

- `safety_stock_units`
- `available_units`
- `forecast_units`
- `inbound_units`

Derived output bounds are also encoded in the Product output schema:

- `projected_units`: `-MAX_INVENTORY_UNIT_VALUE..2×MAX_INVENTORY_UNIT_VALUE`
- `reorder_units`: `0..2×MAX_INVENTORY_UNIT_VALUE`
- `total_reorder_units`: `0..2^53-1`

The JSON decoder uses a product-owned integer-literal digit guard before Python constructs an arbitrary-size integer. Overlong integer literals and values above the business bound return:

```text
HTTP 502
code=COMMERCE_SNAPSHOT_INVALID
retryable=false
```

They fail before protected payload, Submission, Task, Run, Event, Artifact, Evaluation, or model invocation.
