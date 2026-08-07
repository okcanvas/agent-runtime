# STEP027 — Commerce snapshot ingress failure-matrix product acceptance

## Status

`WINDOWS_LIVE_ACCEPTED`

## Code-audited reason

STEP026 is Windows live accepted and proves four valid replenishment states plus duplicate-SKU invalidity. Inspection of `ControlledCommerceHTTPAdapter`, `GovernedCommerceSnapshotIngressService`, Control API error mapping, and existing tests showed that the remaining source/authentication/transport/configuration failure branches were not yet exercised as one Product acceptance boundary.

Expanding to writes, remote origins, another Agent, browser mutation, or distributed execution before proving these existing failures would weaken the accepted read-only source boundary. STEP027 therefore adds no production capability. It only establishes exact external error contracts and proves that every failure occurs before Product persistence or model execution.

## Acceptance cases

- 9 controlled loopback HTTP response failures;
- 1 deterministic transport failure;
- 4 pre-network configuration/request/definition failures.

## Acceptance properties

- exact HTTP status, safe code, and retryable flag per case;
- no redirects followed and no retries issued;
- no source writes;
- no Submission/Task/Run/Event/Artifact/Evaluation;
- no protected payload;
- no model gateway call;
- no credential or failure-body persistence;
- unchanged immutable References;
- Acceptance Workspace cleanup `COMPLETED`.

## Reference decision

No new OpenAI Agents SDK behavior is adopted in this step. The failure boundary occurs before Runner invocation, so existing product code and tests are authoritative. `/reference` remains immutable and unchanged.


## Windows live closure

The user-reported Windows run passed all 24 checks with fourteen exact failure contracts, nine source reads, zero redirect-target reads, one transport attempt, zero writes, zero Product/Evaluation/Artifact/payload/model state, unchanged References, and cleanup `COMPLETED`. See `docs/evidence/STEP027_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`.
