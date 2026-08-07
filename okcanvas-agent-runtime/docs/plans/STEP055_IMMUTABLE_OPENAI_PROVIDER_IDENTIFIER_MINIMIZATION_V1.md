# STEP055 — Immutable OpenAI Provider Identifier Minimization V1

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

Version `2.35.0`.

## Closed prerequisite

The user-reported STEP054 Windows result matched all 30 packaged checks: explicit
`ModelSettings.store=False`, official OpenAI Responses/HTTP route, zero retry, reasoning
minimization, provider lifecycle `1/1/1`, policy drift `409`, final Product counts
`1/1/2/1/10/1/1`, one retained drift payload, Evaluation `PASSED`, unchanged References and
cleanup `COMPLETED` in one attempt. STEP054 is `WINDOWS_LIVE_ACCEPTED`.

## Problem

The installed SDK exposes provider response and request identifiers. The generic Product Runtime
persisted the raw response ID in `model.completed`, `run.completed`, and the execution envelope.
The request ID was already reduced to a boolean. No Product feature used the raw response ID for
resume, evaluation, Artifact verification, Session history or replay.

This created an unnecessary provider-correlation identifier in Product and Evaluation-adjacent
evidence after STEP054 had already disabled request-level response storage.

## Goal

Adopt one immutable provider-identifier policy:

- persist neither provider response ID nor provider request ID;
- retain only boolean presence evidence in the bounded `model.completed` lifecycle Event;
- return `response_id=null` from the generic Product execution envelope;
- bind policy and implementation source identity into the Runtime binding;
- emit safe policy metadata at model start;
- reject policy/source drift before a second Product Task/Run;
- preserve the official route, zero retry, reasoning minimization and `store=false` boundaries.

## Product contracts

1. `specs/runtime/openai-provider-identifier-policy.json` is the only policy.
2. `persist_response_id=false` and `persist_request_id=false` are mandatory.
3. `persist_identifier_presence=true` permits only booleans, never the identifier values.
4. SDK identifiers may exist transiently inside the installed SDK execution, but the Product
   gateway discards `RunResult.last_response_id` at its return boundary.
5. `model.completed` exposes `response_id_present` and `request_id_present`, plus explicit false
   persistence flags; it contains no `response_id` or `request_id` field.
6. `run.completed`, Product DB, Evaluation DB, Artifact and generic execution response contain no
   raw provider identifier.
7. Runtime binding includes policy SHA and combined product source SHA.
8. Confirmation recomputes the binding; policy/source drift returns `409` before Product execution.

## Exact claim boundary

STEP055 minimizes identifiers in OKCanvas Product-owned storage and response contracts. It does not
claim that the provider, SDK process, HTTP client, transport, telemetry, abuse-monitoring or billing
systems never create or retain identifiers. It does not disable SDK-internal transient identity
needed during one active call.

## Non-scope

- universal provider identifier elimination;
- provider-side logs or account data controls;
- prompt-cache keys or retention;
- trace ID removal;
- positive retry, alternate providers, remote MCP, Session transformation, parallel orchestration,
  or Sandbox capability.

## Deterministic acceptance

`python scripts/run_step055_acceptance.py` proves 35/35 checks. A fake SDK returns explicit private
response/request identifier sentinels. Product evidence retains only two `true` presence booleans;
the sentinels are absent from Events, Product/Evaluation DB, Artifact, Runtime binding and Product
execution response. The test also proves official routing, zero retry, reasoning minimization,
`store=false`, successful Artifact/Evaluation, idempotent replay, provider-identifier policy drift
`409`, final counts `1/1/2/1/10/1/1`, one retained drift payload, unchanged References and cleanup
`COMPLETED`.

## Windows closure gate

```bat
cd /d D:\NODE_AGENTS\okcanvas-agent-runtime
sh_setup.cmd
sh_run_step055_acceptance.cmd
```

STEP056 must not be selected before every STEP055 check and cleanup `COMPLETED` are reported.
