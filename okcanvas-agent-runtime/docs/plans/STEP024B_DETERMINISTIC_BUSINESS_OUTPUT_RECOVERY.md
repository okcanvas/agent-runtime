# STEP024B — Deterministic business output recovery

## Status

`WINDOWS_LIVE_ACCEPTED`

## Problem

The first installed-SDK STEP024 run reached `model.completed` and then failed before Artifact
creation. The SDK validates the Pydantic output inside `Runner.run()`, including business
`model_validator` rules that are not expressible in provider JSON Schema. An invalid final output
therefore appears as an SDK failure before the product can classify or persist it.

## Scope

- adopt the official SDK `invalid_final_output` handler;
- restrict recovery to `StoreReplenishmentReviewResult`;
- compute replenishment math deterministically from the original protected snapshot;
- make recovery observable with `agent.output.recovered`;
- keep the existing product JSON round-trip and Artifact validation;
- include safe `detail_type` in failed `/outcome` responses;
- do not retry the model, add Tools, or broaden approval behavior.

## Non-scope

- generic output repair for other Agents;
- external ERP/MCP access;
- inventory or purchase-order writes;
- model-judge repair;
- persistence of raw model output.
