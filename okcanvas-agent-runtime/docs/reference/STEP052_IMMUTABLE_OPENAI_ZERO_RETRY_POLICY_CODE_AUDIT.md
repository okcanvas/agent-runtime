# STEP052 — Code and Immutable Reference Audit

## Audit rule

The STEP051 package, current product call path and immutable
`reference/upstream/openai-agents-python-0.19.0` snapshot were inspected before selecting STEP052.
No executable code imports from `/reference`.

## STEP051 Windows closure

The user report matched all 25 conditions and is compacted in
`docs/evidence/STEP051_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`. STEP051 is Windows-live accepted.

## Candidate comparison

### Selected: immutable zero-retry authority

STEP051's provider wrapper passed API key/base URL to installed-SDK `OpenAIProvider`, which lazily
creates `AsyncOpenAI` with provider defaults. The gateway supplied no explicit SDK
`ModelRetrySettings`. Provider retry and Runner retry identity therefore remained outside Product
Runtime binding.

This gap affects every model call and can duplicate an external request. Closing it adds no new
provider, Tool, transport, filesystem authority or orchestration breadth.

### Deferred: positive bounded retry

The installed SDK supports `ModelRetrySettings`, provider advice and retry policies. Audit also
found that `get_response_with_retry` and `stream_response_with_retry` preserve up to three
conversation-locked compatibility retries whenever `max_retries>0`. That is separate from the
configured policy budget. STEP052 cannot honestly promise a global one-retry maximum while this
path remains enabled for stateful requests.

### Deferred: second provider

Claude, Gemini, LiteLLM and compatible endpoints still require provider-specific authentication,
feature parity, output/error normalization and replay evidence.

### Deferred: reasoning-content persistence

Reasoning replay and provider data have independent sensitivity and retention boundaries and are
not required to establish retry authority.

### Deferred: Sandbox, remote MCP and parallel orchestration

Those add independent containment, transport or cancellation contracts and do not close duplicate
model-request authority.

## Product source findings before change

1. `PinnedOpenAIResponsesProvider` did not set the underlying client's retry count.
2. Root RunConfig contained explicit model/provider but no explicit model retry settings.
3. Agent-as-Tool child RunConfig also omitted retry settings.
4. Runtime binding had model route/provider source identity but no retry policy/source identity.
5. Product Event metadata did not state retry budgets.

## Immutable SDK findings

Inspected paths:

- `reference/CODE_MAP.md` model/retry section;
- `src/agents/retry.py`;
- `src/agents/run_internal/model_retry.py`;
- `src/agents/models/_retry_runtime.py`;
- `src/agents/models/openai_provider.py`;
- `src/agents/models/openai_responses.py`;
- `tests/models/test_model_retry.py`;
- `examples/basic/retry.py`.

Confirmed behavior:

- `ModelRetrySettings.max_retries` counts retries after the initial request;
- a policy callback is independent from provider-managed retries;
- OpenAI model wrappers can call `client.with_options(max_retries=0)` when the Runner disables
  provider retries;
- explicit `max_retries=0` disables Runner retries and the legacy conversation-locked compatibility
  retry path;
- positive retry settings may allow stateful compatibility retries outside the ordinary policy
  count;
- streamed retries are blocked after retry-unsafe events, but STEP052 does not need to rely on that
  gate because it permits no retry at all.

## Implemented files

- `specs/runtime/model-retry-policy.json` — exact zero-retry policy;
- `model_retry/models.py`, `catalog.py`, `runtime.py` — validation, binding and installed-SDK
  settings construction;
- `model_routing/provider.py` — explicit `AsyncOpenAI(max_retries=0)`;
- `execution/openai_gateway.py` — explicit retry settings on Root and child RunConfig plus safe Event
  metadata;
- `execution/runtime_binding.py` — policy and source SHA binding;
- focused unit/baseline tests and STEP052 Acceptance;
- current baseline, plans, roadmap, README and handoff evidence.

## Security and retention

- no raw model error is persisted;
- endpoint and API key remain absent from Events and Product/Evaluation DB;
- one failed model call retains its protected payload under the existing investigation policy;
- success deletes its payload;
- drift retains the unconfirmed payload under existing TTL policy;
- provider and client close through the existing outer gateway `finally`;
- Reference remains immutable.

## Result

STEP052 is implemented and deterministically accepted with 25/25 checks. Windows live acceptance
remains pending.
