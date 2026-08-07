# Commerce snapshot strict scalar types

## Purpose

STEP029 closes an ambiguity in the read-only commerce source contract. `extra="forbid"` rejected unknown fields but Pydantic still coerced compatible scalar values. Numeric strings, booleans, and integral floats could therefore become inventory integers.

## Rule

The external `StoreReplenishmentInput` contract is strict:

- `safety_stock_units`: JSON integer;
- `available_units`: JSON integer;
- `forecast_units`: JSON integer;
- `inbound_units`: JSON integer.

Values such as `"2"`, `true`, and `5.0` are invalid even when they could be converted without losing a mathematical value.

## Failure contract

```text
HTTP 502
code=COMMERCE_SNAPSHOT_INVALID
retryable=false
```

Each invalid response is read once and rejected before canonical preflight, protected payload, Product state, Evaluation, Artifact, or model execution.

## Non-scope

STEP029 adds no source, remote origin, write authority, purchase order, Agent, Tool, MCP, browser mutation, tenant authorization, retry, or distributed worker.

## Windows live acceptance

The user-reported Windows run passed all 18 checks across the four scalar-coercion cases, with four reads, zero writes, zero Product/model state, unchanged References, and cleanup `COMPLETED`.
