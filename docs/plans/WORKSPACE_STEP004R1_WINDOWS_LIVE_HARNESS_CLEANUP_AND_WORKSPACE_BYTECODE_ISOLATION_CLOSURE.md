# WORKSPACE STEP004R1 — Windows Live harness cleanup and Workspace bytecode isolation closure

## Identity

```text
WORKSPACE_STEP004R1_WINDOWS_LIVE_HARNESS_CLEANUP_AND_WORKSPACE_BYTECODE_ISOLATION_CLOSURE
Version 0.4.1
```

## Parent

- Official Windows baseline: `WORKSPACE_STEP003R2` / `0.3.2`, Windows deterministic 27/27.
- Live-readiness parent: `WORKSPACE_STEP004` / `0.4.0`.
- Runtime retained candidate: `STEP087R1` / `2.67.1`.

## Actual Windows inputs

The user's Runtime `.env.local` loaded:

```text
OPENAI_API_KEY=<present; value never persisted>
OKCANVAS_AGENT_MODEL=gpt-4.1
```

The STEP004 Live preflight passed 5/5, so environment loading was not the failure.

## Scope

1. Stop all Live subprocesses and ASGI servers before deleting temporary files.
2. Separate execution errors from cleanup errors.
3. Prevent built-in filesystem `PermissionError` from being reported as OpenAI authentication.
4. Record bounded failure stage and cleanup evidence without raw Provider errors.
5. Apply `PYTHONPYCACHEPREFIX` isolation before Workspace child-interpreter startup.
6. Preserve STEP003R2, STEP087R1 and all deterministic Product boundaries.
7. Keep Live OpenAI and deterministic acceptance as separate commands and evidence.

## Non-scope

- No OpenAI API key value is copied or persisted.
- No model change; the configured model remains `gpt-4.1` on the user's Windows environment.
- No real enterprise Groupware provider; the Live harness retains the actual Connector plus Node API Fake.
- No Runtime Agent topology or product route change.

## Deterministic acceptance

Expected:

```text
state: PASSED
passed_checks: 30
total_checks: 30
Workspace unit tests: 50/50
Deterministic Main Assistant E2E: 14/14
```

## Windows Live acceptance

Expected success:

```text
state: PASSED
passed_checks: 22
total_checks: 22
model: gpt-4.1
actual_openai_model_called: true
harness_cleanup_completed: true
```

On failure, the evidence must retain the original `failure_stage` and safe category, then independently report cleanup completion.
