# Commerce snapshot non-empty inventory

## Purpose

STEP030 prevents an empty inventory scope from being interpreted as a healthy inventory result. Before this step, `items=[]` satisfied `StoreReplenishmentInput`, and the deterministic calculation returned `READY`, `reviewed_skus=0`, and `total_reorder_units=0`.

No inventory rows means the source supplied no business scope to review. It is not evidence that every SKU is covered.

## Rule

A valid `StoreReplenishmentInput` contains between 1 and 100 items.

```text
1 <= len(items) <= 100
```

An empty array is rejected after one source GET and strict JSON validation, before canonical preflight.

## Failure contract

```text
HTTP 502
code=COMMERCE_SNAPSHOT_INVALID
retryable=false
```

No Submission, protected payload, Task, Run, Event, Artifact, Evaluation, or model call may be created.

## Deterministic recovery behavior

If an empty snapshot is supplied directly to the product-owned deterministic calculation boundary, it returns `INSUFFICIENT_DATA` with zero recommendations. It must never return a false `READY` result.

## Non-scope

STEP030 adds no source, remote origin, write authority, purchase order, Agent, Tool, MCP, browser mutation, tenant authorization, retry, or distributed worker.
