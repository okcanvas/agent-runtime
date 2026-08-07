# STEP051 — Immutable OpenAI Model Route Binding V1

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

Version `2.31.0`.

## Closed prerequisite

The user-reported STEP050 Windows launcher output matched every packaged condition. STEP050 is now `WINDOWS_LIVE_ACCEPTED`: 31/31 checks, Session `1/4 → 1/4 → 2/8`, MCP runtime/manager enter/exit/Tool calls `3/3/3/3`, SQLiteSession instances/closes `6/6`, final Product counts `3/3/3/3/39/2/1`, one retained failed payload, Evaluation `PASSED`, Reference unchanged, and workspace cleanup `COMPLETED` in one attempt.

## Problem

Before STEP051, a governed request supplied a plain `model` string. The installed SDK default provider resolution then determined provider, API and endpoint semantics. The Product Runtime fingerprint covered Agent definitions and execution code but did not bind one exact model-provider route or the provider wrapper source.

That left four gaps:

1. a provider-prefixed model string could attempt to select a provider outside product policy;
2. environment or SDK defaults could influence endpoint/API selection;
3. automatic fallback authority was not explicitly denied;
4. preflight confirmation did not fail when the model route policy or provider implementation changed.

## Goal

Implement one immutable route only:

- provider exactly `openai`;
- installed-SDK adapter exactly `agents.models.openai_provider.OpenAIProvider`;
- API exactly Responses;
- transport exactly HTTP;
- base URL exactly `https://api.openai.com/v1`;
- explicit `RunConfig.model` and `RunConfig.model_provider`;
- provider-prefixed model IDs forbidden;
- automatic fallback disabled and fallback list empty;
- sensitive trace data disabled;
- model policy SHA and provider-runtime source SHA included in the Product Runtime binding;
- provider resources explicitly closed.

STEP051 does not claim a provider matrix. The concrete OpenAI model ID remains governed request input, but provider/API/transport/endpoint/fallback semantics are immutable.

## Product contracts

1. `specs/runtime/model-routing-policy.json` is the single exact product-owned route policy.
2. Policy fields are closed; unknown, missing or changed fixed fields fail closed.
3. Model IDs must be concrete, match the bounded pattern and contain no provider prefix separator `/`.
4. Preflight resolves the selected model before persisting a governed submission. An invalid route returns HTTP 422 and creates no preflight row.
5. Runtime binding includes the canonical policy SHA and combined source SHA of the model-routing models, catalog and provider wrapper.
6. Confirmation recomputes the Runtime binding. Policy or provider drift produces an integrity conflict before Task/Run creation.
7. Gateway constructs `PinnedOpenAIResponsesProvider` with explicit API key, official base URL, Responses enabled, Responses WebSocket disabled and strict feature validation enabled.
8. Root and nested Agent-as-Tool RunConfig objects receive the explicit model and same explicit provider object. SDK default provider lookup is not authoritative.
9. The wrapper accepts only the exact selected model ID. A different model request from the SDK fails closed.
10. No automatic fallback, alternate model list, provider prefix, custom base URL or environment-selected endpoint is permitted.
11. `model.started` records safe route identity: provider, API, transport, policy SHA and selected model. Endpoint, API key, prompts, responses and reasoning are prohibited.
12. Provider `aclose()` runs in the outer gateway `finally` after Runner/MCP lifecycle termination and is idempotent.
13. Existing governed replay, protected-payload retention, Artifact and Evaluation boundaries remain unchanged.

## Explicit non-scope

- Claude, Gemini, LiteLLM, AnyLLM or any non-OpenAI provider;
- Azure OpenAI, custom OpenAI-compatible endpoints or organization/project routing;
- automatic fallback, retry-to-another-model or provider failover;
- pricing, quota, budget, quality or latency-based model selection;
- model aliases, dynamic model catalogs or remote policy mutation;
- Responses WebSocket, Chat Completions or Realtime API;
- live external-model quality acceptance;
- secret storage, rotation or tenant-specific credentials;
- cross-provider replay equivalence.

## Deterministic acceptance

Run:

```text
python scripts/run_step051_acceptance.py
```

The acceptance proves:

- provider-prefixed model rejection before preflight persistence;
- one successful governed `coding-agent` execution through the explicit pinned provider;
- exact OpenAI provider constructor arguments and selected model;
- `Runner.run=0`, `Runner.run_streamed=1`;
- provider construct/get-model/close `1/1/1`;
- official endpoint remains authoritative even when `OPENAI_BASE_URL` is hostile;
- automatic fallback and sensitive tracing remain disabled;
- safe model Event metadata with no endpoint or secret;
- one verified Artifact and recorded Evaluation `PASSED`;
- confirmation replay creates no duplicate execution;
- policy drift after preflight returns 409 and creates no second Task/Run;
- final Task/Run/Submission/Invocation/Event/Artifact/Evaluation `1/1/2/1/10/1/1`;
- successful payload deleted, unconfirmed drift payload retained, final payload file count `1`;
- Reference unchanged and workspace cleanup `COMPLETED`.

Required result: 25/25 checks true.

## Windows closure gate

From a fresh extracted ZIP:

```bat
cd /d D:\NODE_AGENTS\okcanvas-agent-runtime
sh_setup.cmd
sh_run_step051_acceptance.cmd
```

STEP052 must not be selected or implemented until the complete Windows STEP051 result is reported, compared with this contract and recorded in the packaged handoff.
