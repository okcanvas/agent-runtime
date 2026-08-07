# STEP055 — Code and Immutable Reference Audit

## Audit rule

The STEP054 package, generic OpenAI execution path and immutable
`reference/upstream/openai-agents-python-0.19.0` snapshot were inspected before selecting STEP055.
No executable code imports from `/reference`.

## STEP054 Windows closure

The user report matched all 30 checks and is compacted in
`docs/evidence/STEP054_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`. STEP054 is Windows-live accepted.

## Candidate comparison

### Selected: provider response/request identifier minimization

Product code persisted `response.response_id` in `model.completed`, propagated
`RunResult.last_response_id` through `GenericGatewayRunResult`, persisted it again in
`run.completed`, and returned it in `GenericExecutionEnvelope`. Repository search found no generic
Product read path that uses the raw identifier for replay, Session continuity, Artifact validation,
Evaluation, recovery or reconciliation. Request identity was already represented only by
`request_id_present`.

The immutable SDK confirms that `ModelResponse.response_id` and `RunResult.last_response_id` are SDK
execution results and that RunState may use response identity internally. Therefore the safe Product
boundary is to leave SDK-internal behavior untouched and discard identifiers only when crossing into
Product-owned evidence.

### Deferred: prompt-cache policy

The immutable SDK can generate prompt-cache keys by default and exposes retention/options fields.
Disabling or governing that behavior requires a separate explicit cache-key and retention design;
it is not required to remove unused Product-persisted provider IDs.

### Deferred: positive retry, alternate providers, Session transformation, parallel execution,
remote MCP and Sandbox

Those add replay, provider parity, history transformation, cancellation, authentication or
containment contracts unrelated to the observed identifier persistence gap.

## Product findings before change

- `model.completed` persisted raw `response_id`;
- `run.completed` persisted raw `gateway_result.response_id`;
- the generic execution envelope returned raw `response_id`;
- raw response identity had no Product consumer;
- request identity was already reduced to `request_id_present`;
- Runtime binding had no provider-identifier policy/source identity.

## Immutable SDK findings

Inspected:

- `src/agents/items.py` (`ModelResponse`);
- `src/agents/result.py` (`last_response_id`);
- `src/agents/run_state.py` response identity serialization;
- OpenAI Responses model adapter and lifecycle tests.

Confirmed:

- the SDK may create and use provider identifiers transiently;
- Product code need not persist them after a completed execution;
- identifier minimization can be implemented without SDK fork or provider behavior change.

## Implemented files

- `specs/runtime/openai-provider-identifier-policy.json`;
- `provider_identity/models.py`, `catalog.py`, `runtime.py`;
- `execution/openai_gateway.py` presence-only lifecycle evidence and Product-boundary discard;
- `execution/runtime_binding.py` policy/source fingerprint;
- focused tests, STEP055 Acceptance, Evaluation case and Windows launcher;
- AGENTS/HANDOFF/PLANS/ROADMAP/README and STEP054 Windows evidence.

## Exact limitation

This implementation proves minimization in Product-owned evidence. It does not claim provider-side
identifier absence, transport zero logging, SDK in-memory nonexistence, trace-ID removal, or
prompt-cache control.

## Acceptance result

35/35 deterministic checks pass. Private response/request identifiers were observed only as boolean
presence and were absent from Product Events, Product/Evaluation DB, Artifact, Runtime binding and
execution response; policy drift returned `409`; final counts were `1/1/2/1/10/1/1`; one drift
payload remained; Evaluation passed; References were unchanged; cleanup completed in one attempt.
Windows live rerun remains pending until reported.
