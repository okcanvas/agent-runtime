# STEP051 — Code and Immutable Reference Audit

## Audit rule

STEP051 was selected only after inspecting the STEP050 packaged source and immutable `reference/upstream/openai-agents-python-0.19.0` snapshot. Executable Runtime code imports nothing from `/reference`.

## STEP050 Windows closure

The user-reported STEP050 JSON was compared with the packaged plan and Acceptance contract. All 31 booleans, Session checkpoints, MCP manager ordering, gateway and Product counts, Evaluation, payload retention, Reference integrity and cleanup matched. The compact record is `docs/evidence/STEP050_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`.

## Candidate comparison

### Selected: immutable OpenAI model route binding

Code audit showed that `RunSubmissionService` accepted a caller-provided model string and `OpenAIAgentGateway` passed the model into Agent construction while allowing the SDK's default provider resolution to remain authoritative. Runtime binding did not include provider/API/endpoint/fallback policy or provider wrapper source.

This was a concrete execution-identity gap affecting every existing Agent capability. Closing it adds no Tool, filesystem, network destination, remote MCP or orchestration breadth beyond the already required OpenAI model call.

### Deferred: multiple providers

Claude, Gemini, LiteLLM, AnyLLM and OpenAI-compatible providers require provider-specific authentication, feature parity, output semantics, error normalization, tracing and replay policy. STEP051 deliberately does not infer interchangeability.

### Deferred: model policy breadth

Dynamic aliases, pricing, budget, quality routing, fallback, retry and tenant-specific model catalogs require independent product contracts and evidence.

### Deferred: Sandbox and file/Shell capability

Containment, mounts, egress, secrets, cleanup and Artifact export remain unresolved and are unrelated to model identity.

### Deferred: parallel orchestration

Concurrency ceilings, cancellation propagation, partial failure and deterministic aggregation remain unresolved.

## Product source findings before change

1. Governed preflight normalized the model string but did not resolve it through an immutable product policy.
2. Gateway had no product-owned `ModelProvider` wrapper.
3. `RunConfig` did not bind one explicit provider object across Root and nested Agent-as-Tool runs.
4. `OPENAI_BASE_URL` or SDK/provider defaults could influence the effective endpoint.
5. Runtime binding omitted model-route policy and provider implementation source.
6. Confirmation therefore could not reject policy/provider drift.
7. Provider lifecycle closure was not a product-owned gateway invariant.

## Immutable SDK findings

Primary inspected paths:

- `.agents/references/model-provider-boundaries.md`;
- `reference/upstream/openai-agents-python-0.19.0/src/agents/models/interface.py`;
- `src/agents/models/openai_provider.py`;
- `src/agents/run.py` and RunConfig resolution;
- `tests/test_run_config.py`.

Observed behavior:

- `ModelProvider` owns `get_model(model_name)` and may expose asynchronous `aclose()`.
- `RunConfig.model` and `RunConfig.model_provider` explicitly override Agent/default model resolution.
- SDK `OpenAIProvider` accepts API key, base URL, Responses selection, Responses WebSocket selection and strict feature validation.
- The provider may own clients/resources and therefore needs an explicit close boundary.
- Provider selection is independent of Agent Tool, Handoff, MCP and Session composition, so one product-owned provider can be supplied consistently to Root and nested runs.

These findings support the narrow STEP051 route; they do not prove compatibility with other providers.

## Implemented code

### `model_routing/catalog.py`

Loads one exact closed JSON policy, validates fixed OpenAI/Responses/HTTP/official-base-url semantics, computes canonical policy SHA and rejects missing, blank, provider-prefixed or pattern-invalid model IDs.

### `model_routing/provider.py`

`PinnedOpenAIResponsesProvider` lazily constructs installed-SDK `OpenAIProvider` with:

```text
base_url=https://api.openai.com/v1
use_responses=true
use_responses_websocket=false
strict_feature_validation=true
```

It accepts only the exact resolved model and implements idempotent asynchronous close.

### `run_submission/service.py`

Preflight calls `resolve_model(normalized_model)` before persistence. Invalid model routes become governed validation errors and HTTP 422 responses without a preflight record.

### `execution/runtime_binding.py`

Binding now includes:

- canonical model-routing policy dictionary and SHA;
- combined SHA of model-routing models/catalog/provider source;
- those source modules in the execution-engine source fingerprint.

Any policy or provider implementation change changes `runtime_binding_sha256`.

### `execution/openai_gateway.py`

The gateway resolves the route, constructs one pinned provider, supplies explicit model/provider in RunConfig, emits safe route metadata and closes the provider in the outer `finally` after execution resources terminate.

### Product metadata

RuntimeInfo declares exact implemented/deterministic state while keeping STEP051 Windows live acceptance false until the user reports the packaged launcher result.

## Acceptance audit finding

The first deterministic STEP051 run proved all substantive product contracts but the Acceptance expected HTTP 400 for a provider-prefixed model. Source inspection of `_raise_submission_error` showed `RunSubmissionValidationError` is contractually HTTP 422. The Acceptance was corrected to the real API contract. A separate evidence expression returned a non-empty SHA string instead of a boolean; it was changed to `len(sha)==64`. No Product Runtime change was required for either correction.

## Safety and persistence review

- The Product DB stores the selected model and immutable Runtime-binding identity, as it already did for governed executions.
- API key and endpoint are not written to Product/Evaluation DB or Events.
- `model.started` contains only route identity and selected model.
- Provider-prefixed routes are denied before preflight persistence.
- Policy drift retains only the encrypted unconfirmed protected payload under the existing TTL policy.
- Successful payload is deleted.
- Reference tree remains immutable and executable code has zero direct `/reference` imports.

## Result

STEP051 is implemented and deterministically accepted with 25/25 checks. Windows live acceptance remains pending.
