# STEP045 Integrated Walking Skeleton Acceptance

## Status

- Version: `2.25.0`
- Executable baseline: `STEP045_INTEGRATED_WALKING_SKELETON_ACCEPTANCE`
- State: `IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`
- Previous closure: STEP044 is Windows live accepted.

## Purpose

Declare the P0 basic Agent Runtime skeleton complete only after the accepted primitives are visible and selectable through one governed Interactive Runner surface and pass one release acceptance matrix. STEP045 adds no second execution engine and no demo-only primitive implementation.

## Product-owned scenario catalog

`specs/runtime/walking-skeleton-scenarios.json` is the immutable closed catalog. It contains exactly ten scenarios in fixed order:

1. Tool-free structured Agent;
2. read-only Function Tool;
3. approval-required Function Tool with separate Approval Operator;
4. read-only MCP Agent;
5. native SDK streaming;
6. native Handoff;
7. Agent-as-Tool;
8. two-turn SQLite Session;
9. native Guardrail rejection;
10. verified Artifact and recorded Evaluation.

Each scenario binds a fixed Agent ID, action mode, request template, Evaluation case when applicable, expected terminal state/error, Session and approval requirements, invocation kinds and `workspace_access=none`. Models, prompts and browser input cannot select Python implementations, host paths or hidden execution routes.

## Interactive Runner integration

The authenticated `GET /v1/runtime-scenarios` endpoint resolves all declared Agent and Evaluation identities before returning the catalog. `/runner` renders a capability matrix and only fills the existing governed form. Selecting a card never auto-confirms, auto-approves or directly calls a Runner.

The Runner continues to use:

- governed preflight;
- exact confirmation;
- separate approval preparation and Approval Operator decision authority;
- native ephemeral stream;
- canonical persisted Event stream;
- verified Artifact API;
- recorded Evaluation API;
- Product Session APIs.

STEP045 also exposes ROOT, HANDOFF and AGENT_AS_TOOL invocation identities, parent relationship, state and workspace absence through the existing invocation API.

## Deterministic acceptance design

The STEP045 acceptance has two layers:

1. one fresh tool-free governed Runner path in the STEP045 workspace;
2. isolated reruns of the actual accepted primitive scripts for STEP037, STEP038, STEP039, STEP041, STEP042, STEP043 and STEP044.

Sub-acceptances run only from `scripts/run_step045_acceptance.py`; executable Runtime source contains no call to STEP scripts. This release matrix reuses the real product paths instead of replacing them with a combined fake execution engine.

## Completion declaration

`BASIC_AGENT_RUNTIME_SKELETON_COMPLETE` is valid only when all 28 STEP045 checks pass, the catalog contains ten scenarios, all seven primitive reruns pass and clean up, the governed tool-free path succeeds, the Artifact is verified, the ROOT invocation is visible, the payload is deleted, References are unchanged and the STEP045 acceptance workspace cleanup is `COMPLETED`.

## Explicit non-scope after P0

STEP045 does not add:

- mixed capability graphs;
- multiple/chained Handoffs;
- repeated/nested/parallel Agent Tools;
- Session with Handoff, Agent Tool, Tool, MCP or approval;
- physical workspace or Sandbox;
- hosted Tools;
- parallel orchestration;
- remote Session backends;
- Session encryption/compaction;
- realtime, voice or Computer Use.

Those are P1/P2 candidates and require new code audit, policy and acceptance.

## Windows closure

Run:

```bat
cd /d D:\NODE_AGENTS\okcanvas-agent-runtime
sh_setup.cmd
sh_run_step045_acceptance.cmd
```

Required: `state=PASSED`, `skeleton_state=BASIC_AGENT_RUNTIME_SKELETON_COMPLETE`, all 28 checks true, ten scenarios, seven primitive acceptances all PASSED, tool-free Product counts `1/1/1/1/10/1` for Task/Run/Submission/Invocation/Event/Artifact, payload deleted, References unchanged and cleanup `COMPLETED`.
