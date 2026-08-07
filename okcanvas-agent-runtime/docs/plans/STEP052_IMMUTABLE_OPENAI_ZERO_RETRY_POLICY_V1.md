# STEP052 — Immutable OpenAI Zero-Retry Policy V1

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

Version `2.32.0`.

## Closed prerequisite

The user-reported STEP051 Windows output matched all 25 packaged checks: one explicit OpenAI
Responses/HTTP route, provider construct/get-model/close `1/1/1`, policy drift confirmation `409`,
final Product counts `1/1/2/1/10/1/1`, one retained drift payload, Evaluation `PASSED`, Reference
unchanged and cleanup `COMPLETED` in one attempt. STEP051 is `WINDOWS_LIVE_ACCEPTED`.

## Problem

STEP051 fixed provider/API/transport/endpoint/fallback identity, but retry authority was still partly
implicit:

1. the SDK-created OpenAI client used provider defaults, whose normal retry budget is not Product
   Runtime policy;
2. no explicit `ModelRetrySettings` was supplied through `RunConfig`;
3. installed SDK 0.19.0 preserves a conversation-locked compatibility retry path unless
   `max_retries=0` is explicit;
4. provider and Runner retries were not represented independently in Runtime binding.

A failed model request could therefore be issued more than once without the Product Runtime having
an immutable retry policy or exact evidence for the additional attempt.

## Goal

Own one exact zero-retry policy before considering bounded retries:

- provider-managed retry budget exactly `0`;
- Runner-managed retry budget exactly `0`;
- SDK `retry_policies.never()` supplied explicitly;
- conversation-locked compatibility retries disabled through `max_retries=0`;
- retryable category list empty;
- automatic model fallback remains disabled;
- policy SHA and retry implementation source SHA included in Runtime binding;
- safe retry identity included in `model.started`;
- provider/client resources still closed explicitly.

## Product contracts

1. `specs/runtime/model-retry-policy.json` is the only retry policy.
2. Fixed semantics are closed: both retry budgets `0`, no categories, no compatibility retry and no
   fallback.
3. Policy version may advance only to create a new binding; changing it invalidates pending
   confirmations.
4. The provider wrapper constructs `AsyncOpenAI` with the official base URL and `max_retries=0`, then
   supplies that client to installed-SDK `OpenAIProvider`.
5. Root and explicit child RunConfig objects receive
   `ModelSettings(retry=ModelRetrySettings(max_retries=0, policy=never))`.
6. A network-like failure remains one failed Product Run; the Runtime does not create a replacement
   Task/Run and does not issue a second model attempt.
7. `model.started` persists only policy ID/SHA and numeric retry budgets. Raw error, endpoint and
   secret remain prohibited.
8. Retry policy or implementation drift fails confirmation before another Task/Run is created.
9. Existing Session, MCP, Handoff, Agent-as-Tool, Guardrail, approval and replay boundaries remain
   unchanged.

## Why bounded retry is deferred

Installed SDK 0.19.0 allows runner-managed retry but also preserves a separate
`conversation_locked` compatibility path whenever `max_retries>0`. A product claim such as “at most
one retry” would therefore be false for stateful requests unless that compatibility behavior is
separately governed or wrapped. STEP052 chooses exact zero retries rather than claiming an
unprovable bounded retry contract.

## Explicit non-scope

- any positive retry budget;
- HTTP status, rate-limit, timeout or provider-suggested retry;
- exponential backoff or jitter;
- model/provider fallback;
- replacement Product Run;
- retry after emitted response/tool events;
- stateful Session replay;
- remote provider or custom endpoint;
- live network failure testing.

## Deterministic acceptance

Run:

```text
python scripts/run_step052_acceptance.py
```

The acceptance proves 25 checks:

- exact policy and retry runtime bound;
- Runner and provider retry budgets `0/0`;
- explicit never policy returns false for a simulated network failure;
- failed and successful governed Runs each issue exactly one model attempt;
- official endpoint, Responses HTTP and strict validation remain fixed;
- provider/client construct/get-model/close counts are exact;
- failed Run creates no Artifact;
- successful Artifact and recorded Evaluation pass;
- replay creates no duplicate;
- retry policy drift returns `409` before a third Task/Run;
- safe model Event retry metadata;
- final Product counts `2/2/3/2/18/1/1`;
- failed and drift payloads retained, successful payload deleted, final files `2`;
- Reference unchanged and cleanup `COMPLETED`.

## Windows closure gate

From a fresh extracted ZIP:

```bat
cd /d D:\NODE_AGENTS\okcanvas-agent-runtime
sh_setup.cmd
sh_run_step052_acceptance.cmd
```

STEP053 must not be selected until all 25 checks and cleanup `COMPLETED` are reported and recorded.
