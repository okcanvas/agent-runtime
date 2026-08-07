# STEP028 — Commerce snapshot identity consistency

## Status

`WINDOWS_LIVE_ACCEPTED`

## Code-audited reason

STEP027 is Windows live accepted and closes the ingress failure matrix. Inspection of
`ControlledCommerceHTTPAdapter.acquire()` then found that the source response was validated against
`StoreReplenishmentInput`, but `snapshot.snapshot_id` was never compared with the normalized
`snapshot_key` used in the GET path.

The submission fingerprint contained both the source-request SHA and source-snapshot SHA, so the bytes
were bound, but the product had not proven that the returned business object was the exact object
requested. Expanding authority before closing this identity gap would weaken the existing read-only
boundary.

## Implemented rule

The adapter now requires exact equality between the returned `snapshot_id` and requested normalized
`snapshot_key` before canonical JSON, protected-payload creation, or Product persistence.

Mismatch uses a dedicated safe contract:

```text
HTTP 502
COMMERCE_SNAPSHOT_IDENTITY_MISMATCH
retryable=false
```

The error message does not echo the returned identifier.

## Deterministic acceptance

`STEP028_ACCEPTANCE.json` proves one actual loopback GET returning a valid but differently identified
snapshot. Acceptance requires 15/15 checks, one read, zero writes, all Product/Evaluation counts zero,
zero Artifact and protected-payload files, zero model calls, no credential or returned-identity
persistence, unchanged References, and cleanup `COMPLETED`.

## Reference decision

No OpenAI Agents SDK behavior is involved. The mismatch is rejected before Runner invocation, so
product code and deterministic HTTP acceptance are authoritative. `/reference` remains immutable.

## Windows live closure

The user-reported `sh_run_step028_acceptance.cmd` output passed all 15 checks with the exact mismatch contract, one source read, zero writes, zero Product/model state, unchanged References, and cleanup `COMPLETED`. Compact Evidence is `docs/evidence/STEP028_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`.
