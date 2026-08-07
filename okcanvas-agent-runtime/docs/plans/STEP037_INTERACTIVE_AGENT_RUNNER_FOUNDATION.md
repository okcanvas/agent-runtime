# STEP037_INTERACTIVE_AGENT_RUNNER_FOUNDATION

Status: **IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING**

Version: `2.17.0`

## Purpose

Expose the already-governed single-Agent Runtime as one usable local execution surface without
creating a second execution engine or weakening authority separation.

## Code-audited starting point

Before STEP037, the repository already had:

- an immutable Agent Definition catalog;
- separate local-admin and Run-submitter authenticators;
- governed preflight, encrypted protected payload, exact confirmation, and Task/Run scheduling;
- persisted canonical Events and cursor-resumable SSE;
- immutable final-output Artifacts;
- recorded-Run Evaluation with Runtime-binding verification;
- a read-only Operations Console and a separate Approval Operator.

The missing product surface was a runner that connected those existing boundaries. The general
Operations Console remained intentionally read-only, so adding mutation controls there would have
collapsed separate authorities.

## Implemented boundary

`GET /runner` serves server-owned static assets under
`src/okcanvas_agent_runtime/interactive_runner/assets/`.

The Runner supports:

1. separate entry of `X-OKCanvas-Admin-Key` and
   `X-OKCanvas-Run-Submitter-Key`;
2. Agent catalog and compatible Evaluation Case discovery;
3. governed `POST /v1/run-submissions/preflight`;
4. display of Agent Definition, request fingerprint, Runtime-binding SHA, and protected-payload
   state;
5. exact confirmation followed by the existing governed scheduling path;
6. preparation of the existing Local Tool approval path without making an approval decision;
7. authenticated persisted Event SSE and terminal Run observation;
8. verified final-output Artifact display through the new read-only
   `GET /v1/runs/{run_id}/artifact` API;
9. recorded-Run Evaluation through the existing Evaluation API.

The UI stores only the two authority keys in current-tab `sessionStorage`. It never stores the
request, confirmation challenge, Artifact, or model output in browser storage.

## Authority constitution

- `/runner`: governed Run-submitter surface.
- `/console`: read-only local-admin Operations surface.
- Approval Operator: approval/denial decision surface.

The Runner does not call the direct `POST /v1/runs` API and contains no Tool approval decision
endpoint. It may prepare an approval request because that is part of Run submission; the decision
remains separate.

## Artifact read API

`GET /v1/runs/{run_id}/artifact`:

- requires local-admin authority;
- resolves the Artifact only from the recorded `artifact.created` Event;
- verifies persisted file hash and byte length;
- rejects a path outside the configured Artifact root;
- accepts only `application/json` final-output Artifacts;
- returns metadata and parsed JSON but never exposes `storage_path`.

## Explicit non-scope

STEP037 does not add:

- SDK `run_streamed()` model deltas;
- Handoff, Agent-as-Tool, Session, Guardrails, or parallel orchestration;
- browser approval decisions;
- a second Product Task/Run store;
- direct ungovened model execution;
- remote deployment or multi-user authentication.

Persisted Event SSE is an observation mechanism. Native SDK streaming remains STEP039.

## Deterministic acceptance

`sh_run_step037_acceptance.cmd` uses a deterministic Reference MCP Agent gateway and exercises the
actual Control API boundary:

- Runner shell/assets and CSP;
- separate authority enforcement;
- Agent and Evaluation catalogs;
- governed preflight with no Task/Run before confirmation;
- wrong confirmation rejection;
- exact confirmation and one gateway call;
- persisted canonical Events;
- verified Artifact API;
- Runtime-bound recorded Evaluation;
- successful protected-payload deletion;
- unchanged immutable References.

The current deterministic result is 24/24 PASS with cleanup `COMPLETED`.

## Windows closure

```bat
cd /d D:\NODE_AGENTS\okcanvas-agent-runtime
sh_setup.cmd
sh_run_step037_acceptance.cmd
```

Do not begin STEP038 until the Windows result passes all 24 checks.
