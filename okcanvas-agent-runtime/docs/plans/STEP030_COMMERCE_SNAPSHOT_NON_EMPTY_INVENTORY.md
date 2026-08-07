# STEP030 — Commerce snapshot non-empty inventory

## Status

`WINDOWS_LIVE_ACCEPTED`

## Code-audited reason

After STEP029 Windows closure, direct execution of `StoreReplenishmentInput.model_validate()` proved that `items=[]` was accepted. Direct execution of `build_store_replenishment_result()` then produced `READY`, zero reviewed SKUs, and zero reorder units.

This conflated absent inventory scope with a valid fully covered inventory snapshot.

## Implemented rule

`StoreReplenishmentInput.items` now has:

```python
Field(min_length=1, max_length=100)
```

The canonical invalid fixture is `case006-invalid-empty-items`.

## Deterministic acceptance

`STEP030_ACCEPTANCE.json` proves:

- one actual loopback GET for `case006-invalid-empty-items`;
- HTTP 502, `COMMERCE_SNAPSHOT_INVALID`, `retryable=false`;
- zero source writes;
- zero Submission, Task, Run, Event, Artifact, Evaluation, protected payload, and model gateway calls;
- no credential or invalid snapshot identity persisted in SQLite;
- unchanged References;
- cleanup `COMPLETED`.

## Reference decision

No OpenAI Agents SDK behavior is involved. Rejection occurs before Runner invocation. Product code and deterministic HTTP acceptance are authoritative; `/reference` remains immutable.
