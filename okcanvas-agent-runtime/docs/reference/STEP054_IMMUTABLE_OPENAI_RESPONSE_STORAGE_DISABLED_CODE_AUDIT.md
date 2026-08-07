# STEP054 — Code and Immutable Reference Audit

## Audit rule

The STEP053 package, the generic OpenAI execution path and immutable
`reference/upstream/openai-agents-python-0.19.0` snapshot were inspected before selecting STEP054.
No executable code imports from `/reference`.

## STEP053 Windows closure

The user report matched all 30 checks and is compacted in
`docs/evidence/STEP053_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`. STEP053 is Windows-live accepted.

## Candidate comparison

### Selected: request-level OpenAI Responses storage disablement

The installed SDK's `src/agents/model_settings.py` documents that Responses API storage is
automatically enabled when `ModelSettings.store` is unspecified. The Product's Root and explicit
Agent-as-Tool child `ModelSettings` supplied retry and reasoning fields but omitted `store`.
`src/agents/models/openai_responses.py` passes the non-null setting directly to the Responses create
request. This is an observed provider-default dependency and can be closed without adding new
execution authority.

### Deferred: positive retry

The immutable SDK still has stateful and conversation-locked compatibility behavior when positive
retry is enabled. A safe bounded retry requires a separate replay classification and state design.

### Deferred: alternate providers, Session transformation, parallel execution, remote MCP, Sandbox

Those add provider parity, history transformation, cancellation, authentication or containment
contracts unrelated to the response-storage request gap.

## Product findings before change

- route/provider/API/transport were immutable;
- provider and Runner retry budgets were exactly zero;
- reasoning summary/includes were explicitly disabled;
- `ModelSettings.store` was not supplied anywhere in `OpenAIGenericAgentGateway`;
- Runtime binding had no response-storage policy/source identity;
- no lifecycle Event proved the request-level storage choice.

## Immutable SDK findings

Inspected:

- `reference/upstream/openai-agents-python-0.19.0/src/agents/model_settings.py`;
- `reference/upstream/openai-agents-python-0.19.0/src/agents/models/openai_responses.py`;
- related ModelSettings coercion tests and request-building code.

Confirmed:

- `store: bool | None` controls generated response storage;
- the SDK comment states Responses storage is automatically enabled when unspecified;
- `_build_response_create_kwargs()` forwards a non-null `store` value into the Responses request;
- explicit `False` is representable through normal installed-SDK `ModelSettings` with no fork.

## Implemented files

- `specs/runtime/openai-response-storage-policy.json`;
- `response_storage/models.py`, `catalog.py`, `runtime.py`;
- `execution/openai_gateway.py` explicit Root/child/Tool-bearing `store=False` settings and safe Event
  metadata;
- `execution/runtime_binding.py` policy/source fingerprint;
- focused tests, STEP054 Acceptance, Evaluation case and Windows launcher;
- AGENTS/HANDOFF/PLANS/ROADMAP/README and STEP053 Windows evidence.

## Exact limitation

This implementation proves the outgoing SDK request setting, not universal provider erasure or
zero operational retention. Prompt caching, provider response/request IDs and external account-level
data controls remain outside STEP054.

## Acceptance result

30/30 deterministic checks pass. Root `ModelSettings.store` was captured as exactly `False`; the
official route, zero retry and reasoning minimization remained exact; policy drift returned `409`
before a second Task/Run; final Product counts were `1/1/2/1/10/1/1`; one drift payload remained;
Evaluation passed; References were unchanged; cleanup completed in one attempt. Windows live rerun
remains pending until reported.
