# STEP053 — Immutable Reasoning Evidence Minimization V1

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

Version `2.33.0`.

## Closed prerequisite

The user-reported STEP052 Windows result matched all 25 packaged checks, exact retry budgets `0/0`,
model attempts `2`, final Product counts `2/2/3/2/18/1/1`, two retained payloads, drift `409`,
Evaluation `PASSED`, unchanged References and cleanup `COMPLETED` in one attempt. STEP052 is
`WINDOWS_LIVE_ACCEPTED`.

## Problem

The Runtime already retained the numeric `reasoning_tokens` usage field and filtered raw reasoning
from the native stream, but reasoning evidence policy was implicit:

1. no product-owned policy stated whether reasoning summaries or additional response fields could be
   requested;
2. reasoning summary/content/ID/encrypted/provider-data persistence prohibitions were not part of the
   Runtime binding;
3. `model.completed` did not prove that a returned reasoning item was reduced to safe count-only
   evidence;
4. policy drift could not independently invalidate a pending confirmation.

## Goal

Adopt one minimization policy:

- request no reasoning summary;
- request no additional reasoning response includes;
- persist no reasoning content, summary, item ID, encrypted content or provider data;
- permit only non-content reasoning item count and aggregate reasoning token count;
- bind policy and implementation source SHA;
- preserve sensitive tracing disabled and the STEP051/052 route/retry boundaries.

## Product contracts

1. `specs/runtime/reasoning-evidence-policy.json` is the only policy.
2. Root and explicit Agent-as-Tool child `ModelSettings` carry `reasoning=None` and
   `response_include=[]`.
3. Returned reasoning items may be counted by type only. Product code must not read their summary,
   content, ID, encrypted content or provider data.
4. `model.started` exposes policy identity and booleans only.
5. `model.completed` may expose reasoning item count plus explicit non-persistence evidence.
6. `run.completed.usage.reasoning_tokens` remains allowed as an aggregate integer.
7. Runtime binding includes policy SHA and combined source SHA. Drift fails confirmation before a
   second Task/Run.
8. Artifact, Product DB, Evaluation DB and canonical Events must contain none of the raw reasoning
   sentinel values used by deterministic acceptance.

## Non-scope

- exposing chain-of-thought or reasoning summaries;
- encrypted reasoning replay;
- reasoning-item persistence in Session history policy;
- reasoning quality scoring;
- reasoning effort routing;
- positive model retry, second provider, Sandbox or parallel orchestration.

## Deterministic acceptance

`python scripts/run_step053_acceptance.py` proves 30/30 checks. The fake installed-SDK result
contains one reasoning item with private summary, content, ID, encrypted content and provider data.
Only reasoning item count `1` and reasoning token count `11` may survive. Final Product counts are
`1/1/2/1/10/1/1`, one drift payload remains, drift returns `409`, References remain unchanged and
cleanup is `COMPLETED`.

## Windows closure gate

```bat
cd /d D:\NODE_AGENTS\okcanvas-agent-runtime
sh_setup.cmd
sh_run_step053_acceptance.cmd
```

STEP054 must not be selected before all 30 checks and cleanup `COMPLETED` are reported.
