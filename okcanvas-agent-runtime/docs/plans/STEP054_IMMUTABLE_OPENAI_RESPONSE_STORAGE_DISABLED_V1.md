# STEP054 — Immutable OpenAI Response Storage Disabled V1

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

Version `2.34.0`.

## Closed prerequisite

The user-reported STEP053 Windows result matched all 30 packaged checks, observed one reasoning item
and 11 aggregate reasoning tokens without persisting private reasoning fields, final Product counts
`1/1/2/1/10/1/1`, drift `409`, one retained payload, Evaluation `PASSED`, unchanged References and
cleanup `COMPLETED` in one attempt. STEP053 is `WINDOWS_LIVE_ACCEPTED`.

## Problem

The installed SDK declares `ModelSettings.store` as the Responses API response-storage switch and
states that Responses storage is automatically enabled when the value is unspecified. The Product
Runtime did not set this field. Therefore STEP051–053 fixed route, retry and reasoning evidence but
still delegated the request-level response-storage choice to the provider default.

## Goal

Adopt one immutable request policy:

- use the existing OpenAI Responses/HTTP route only;
- set SDK `ModelSettings.store=False` for the Root RunConfig;
- set the same value for the explicit Agent-as-Tool child RunConfig and Tool-bearing Agent settings;
- bind policy and implementation source SHA into the Runtime binding;
- expose only safe policy identity and the boolean request value in model lifecycle metadata;
- reject policy/source drift before a second Product Task/Run.

## Product contracts

1. `specs/runtime/openai-response-storage-policy.json` is the only policy.
2. The policy value is exactly `response_store_requested=false`.
3. Every `ModelSettings` created by `OpenAIGenericAgentGateway` carries `store=False`.
4. `model.started` may expose policy ID/SHA and `response_store_requested=false` only.
5. Runtime binding includes policy SHA and combined product source SHA.
6. Confirmation recomputes the binding; policy or source drift returns `409` before Product
   execution.
7. STEP051 official route, STEP052 zero retry and STEP053 reasoning minimization remain unchanged.

## Exact claim boundary

`store=False` is a request-level Responses API control. STEP054 does **not** claim that OpenAI or any
network intermediary retains no operational, abuse-monitoring, billing or legal records. It also
does not remove the existing provider response ID from Product completion evidence; identifier
minimization is a separate future boundary if code audit selects it.

## Non-scope

- provider-wide zero retention claims;
- API data-control configuration outside this request field;
- prompt-cache retention policy;
- response/request identifier minimization;
- custom metadata policy;
- positive retry, alternate providers, remote MCP, Session compaction, parallel orchestration or
  Sandbox capability.

## Deterministic acceptance

`python scripts/run_step054_acceptance.py` proves 30/30 checks. It captures Root
`ModelSettings.store == False`, preserves the exact route/zero-retry/reasoning settings, verifies
safe lifecycle metadata, successful Artifact/Evaluation, idempotent replay, response-storage policy
drift `409`, final counts `1/1/2/1/10/1/1`, one retained drift payload, unchanged References and
cleanup `COMPLETED`.

## Windows closure gate

```bat
cd /d D:\NODE_AGENTS\okcanvas-agent-runtime
sh_setup.cmd
sh_run_step054_acceptance.cmd
```

STEP055 must not be selected before all 30 checks and cleanup `COMPLETED` are reported.
