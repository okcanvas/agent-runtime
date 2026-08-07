# Store Replenishment Review Agent

## Purpose

`store-replenishment-review-agent` is the first business-shaped Agent in the runtime. It accepts one immutable store inventory snapshot and returns a structured replenishment review. It is deliberately read-only and has no Tool, MCP, Handoff, SDK Session, filesystem, network, or mutation capability.

## Input contract

The supplied JSON contains:

- `snapshot_id`;
- one non-negative integer `safety_stock_units`;
- at least one unique SKU row with `available_units`, `forecast_units`, and `inbound_units`.

The input remains a protected payload. SQLite stores only hashes and opaque references.

## Calculation contract

For every valid SKU:

```text
projected_units = available_units + inbound_units - forecast_units
reorder_units = max(forecast_units + safety_stock_units - available_units - inbound_units, 0)
```

Positive reorder quantity yields `REORDER / SHORTAGE`; zero yields `NO_ACTION / COVERED`. Recommendations are sorted by reorder quantity descending and SKU ascending. The Pydantic output contract rejects incorrect equations, totals, status, duplicate SKUs, or ordering.

## Governed execution

```text
preflight
→ encrypted protected payload
→ exact fingerprint confirmation
→ one Task and Run
→ installed Agents SDK
→ structured output Artifact
→ deterministic recorded-Run evaluation
→ successful payload deletion
```

## Explicit non-scope

- ERP or commerce API connection;
- inventory writes or purchase-order creation;
- autonomous replenishment;
- model-selected Tools;
- Handoff or multi-Agent routing;
- pricing, revenue, or supplier optimization;
- browser submission controls.


## STEP024A live output boundary

The installed-SDK acceptance does not infer an empty Artifact from a missing file. It records the
terminal Product Run, safe `/outcome` response, exact Artifact count, and bounded validation error.
Before persistence, the returned SDK object is serialized with the output contract's Pydantic
`TypeAdapter`, validated from JSON, and only then written. Empty or invalid serialized output fails
closed with `OUTPUT_CONTRACT_INVALID` and creates no Artifact.


## STEP024B deterministic invalid-final-output recovery

OpenAI Agents SDK `AgentOutputSchema.validate_json()` validates the configured Pydantic type inside
`Runner.run()`. Business-only `model_validator` rules such as exact arithmetic and ordering can
therefore reject a model response after `model.completed` and before a Product Artifact exists.

STEP024B keeps that fail-closed boundary but installs the official SDK
`error_handlers["invalid_final_output"]` callback only for
`StoreReplenishmentReviewResult`. The callback does not call the model again. It parses the same
protected snapshot and applies product-owned deterministic formulas, status rules, uniqueness, and
ordering. A recovered result is validated again by the product JSON round-trip before persistence.

Recovery is observable through `agent.output.recovered`; raw model output is not stored. Other Agent
contracts retain their existing failure behavior. Invalid or ambiguous source snapshots produce
`INSUFFICIENT_DATA` with bounded field/type diagnostics rather than guessed business numbers.

## Windows live acceptance

The corrected installed-SDK run is accepted. It completed one Product Run with
`output_recovered=true`, exact recommendations 12/7/0, total 19, one verified Artifact, a PASSED
recorded-Run Evaluation, no Tool or MCP Event, protected-payload deletion, unchanged references, and
Acceptance Workspace cleanup `COMPLETED`.

The next integration must preserve this source-of-truth boundary. An external commerce snapshot must
be acquired and strictly validated before it is hashed, encrypted, and presented for exact
confirmation. The current Agent must not be changed to calculate from an unbound model-driven MCP
Tool result.


## STEP025 governed external snapshot ingress

The Agent remains unchanged and still has no Tool or MCP. A product-owned loopback HTTP adapter now
acquires the complete `StoreReplenishmentInput` before governed preflight. The validated canonical
snapshot is encrypted as the existing protected request; adapter identity, source-request hash, and
snapshot hash are bound into the exact confirmation fingerprint. Same-key replay does not read the
source again.
