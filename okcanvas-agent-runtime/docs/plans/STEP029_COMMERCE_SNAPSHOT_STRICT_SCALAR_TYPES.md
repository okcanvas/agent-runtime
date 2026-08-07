# STEP029 — Commerce snapshot strict scalar types

## Status

`WINDOWS_LIVE_ACCEPTED`

## Code-audited reason

After STEP028 Windows closure, direct execution of `StoreReplenishmentInput.model_validate()` showed that the model used `ConfigDict(extra="forbid")` without strict mode. Pydantic accepted numeric strings, booleans, and integral floats for integer inventory fields.

The source contract was documented as strict, so implicit coercion was an integrity defect rather than a feature request.

## Implemented rule

The shared input base model now uses:

```python
ConfigDict(extra="forbid", strict=True)
```

This applies to the snapshot and nested item models.

## Deterministic acceptance

`STEP029_ACCEPTANCE.json` proves four actual loopback GETs:

- string `safety_stock_units`;
- boolean `available_units`;
- float `forecast_units`;
- string `inbound_units`.

All must fail with HTTP 502, `COMMERCE_SNAPSHOT_INVALID`, `retryable=false`; source writes and every Product/Evaluation/Artifact/payload/model count remain zero; References remain unchanged; cleanup is `COMPLETED`.

## Reference decision

No OpenAI Agents SDK behavior is involved. Rejection occurs before Runner invocation. Product code and deterministic HTTP acceptance are authoritative; `/reference` remains immutable.

## Windows live acceptance

`sh_run_step029_acceptance.cmd` passed all 18 checks with four source reads, zero writes, zero Product/model state, unchanged References, and cleanup `COMPLETED`.
