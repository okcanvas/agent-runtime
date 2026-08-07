# OR-ISSUE-050 — STEP081B Architecture path and route topology checks were not cross-platform reconciled

## Status

`FIX_IMPLEMENTED_DETERMINISTIC_VALIDATION_PENDING_WINDOWS_RERUN`

## Evidence boundary

The supplied STEP081B output proves Architecture `36/38` and a failed route/topology aggregate, but it does not preserve the two false Architecture check names. Therefore the exact Windows sub-cause is unknown and is not guessed.

## Code audit findings

Two platform-sensitive validation assumptions existed:

1. Project-root ownership used resolved-path object equality rather than same-file identity, which is brittle across Windows junctions, casing and editable-install path representations.
2. Route topology relied only on framework runtime route objects and hardcoded counts, without reconciling the Product source declarations to actual registered `/v1` method/path pairs.

## Fix

- Path ownership uses `os.path.samefile` with normalized real-path fallback.
- Admin and Service route declarations are extracted from source AST.
- Runtime `/v1` routes are normalized and compared exactly with source method/path pairs.
- Source and runtime duplicates, WebSocket declarations, missing routes and unexpected routes are all preserved in Architecture evidence.

The Windows rerun remains authoritative for confirming whether this closes the observed `36/38` failure.

## Recurrence gates

- STEP081C Architecture 38/38
- source/runtime route reconciliation tests
- isolated Windows deterministic Acceptance
