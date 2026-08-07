# WORKSPACE-ISSUE-033 — STEP008 lacked short-expression Windows Live OpenAI acceptance

## Status

```text
FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTANCE_PENDING
WINDOWS_LIVE_OPENAI_RERUN_PENDING
```

## Observed failure

`sh_run_workspace_step008_acceptance.cmd` existed and passed the deterministic Workspace gate, but
there was no `sh_run_workspace_step008_live_acceptance.cmd`. The deterministic evidence explicitly
reported `live_openai_model_called=false`, so it could not promote STEP008 as a Windows Live OpenAI
baseline.

The existing STEP007R1 Live harness was run manually against the STEP008 source. It called the real
configured OpenAI model, Connector and Node Example, but finished `FAILED 19/24`: the first turn
succeeded, while the second same-name turn failed after MCP completion with
`SDK_RUN_FAILED / ModelBehaviorError`. That harness also used explicit "조직 문맥" wording and did
not prove STEP008's new hint-free short-expression routing.

## Root cause

STEP008 implemented and deterministically accepted the routing policy but omitted the corresponding
Live acceptance surface. The available STEP007R1 harness validated the previous explicit-domain
prompts, not these STEP008 expressions:

```text
김민수 정보
김선임 연락처
김민수 직책
과장들 목록
```

## Correction

STEP008R1 adds a Workspace-owned Live harness and launcher without changing the Runtime product
baseline:

```text
sh_run_workspace_step008_live_acceptance.cmd
→ workspace_python_bytecode_isolation.py
→ run_workspace_step008_live_entrypoint.py
→ existing Runtime .env.local loader
→ run_workspace_step008_live_acceptance.py
```

The harness performs two distinct proofs:

1. Product routing preflight proves each short utterance produces the exact
   `okcanvas-organization-context-request-hint-v1` and selects the existing Session Root.
2. Live execution proves actual OpenAI model events, Root Agent-as-Tool, Child MCP invocation,
   expected resolve/search operation, Connector/Node Example reachability, output semantics,
   ambiguity preservation and secret minimization.

Failures retain only bounded diagnostic fields (`code`, `detail_type`, `retryable`, Tool failure
category and stage). Raw provider errors, Tool arguments and Tool results remain unpersisted.

## Recurrence gate

A Workspace step that changes model-facing routing is not promotable as Windows Live accepted unless
it contains a current-step Live launcher and harness that executes the newly admitted utterances
through the configured OpenAI model and actual owned integration boundaries.
