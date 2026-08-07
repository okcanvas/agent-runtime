# STEP031_COMMERCE_SNAPSHOT_BOUNDED_QUANTITIES

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

## Evidence before implementation

After STEP030 and STEP030A Windows closure, direct execution against the current code proved:

- `StoreReplenishmentInput` accepted 1,000-digit non-negative integer quantities;
- `build_store_replenishment_result()` then raised a Pydantic `ValidationError` because the generated reason exceeded 1,000 characters;
- the HTTP adapter did not own an integer-literal length guard and did not catch every `ValueError` produced by JSON integer parsing.

This was a Product contract defect, not an SDK behavior question. No `/reference` implementation was adopted.

## Scope

- introduce one product-owned numeric limit module;
- derive the per-field maximum from `2^53-1`, the 100-item maximum, and the worst-case two-term replenishment sum;
- apply exact upper bounds to input and output contracts;
- reject overlong JSON integer literals before arbitrary-size integer construction;
- add Product-level failure acceptance for all four quantity fields and one overlong integer literal;
- preserve read-only ingress, exact identity, protected-payload, approval, Artifact, Evaluation, and no-write boundaries.

## Explicitly not included

- inventory writes;
- purchase-order creation;
- remote source origins;
- additional business Agents;
- configurable tenant-specific quantity limits;
- automatic retry;
- browser mutation controls.

## Acceptance

`sh_run_step031_acceptance.cmd` must report:

- `state=PASSED`;
- all 19 checks true;
- `case_count=5`;
- all cases HTTP 502 / `COMMERCE_SNAPSHOT_INVALID` / retryable=false;
- source read count 5 and write count 0;
- zero Product/Evaluation counts;
- zero Artifacts, protected payload files, and model calls;
- unchanged References;
- cleanup `COMPLETED`.
