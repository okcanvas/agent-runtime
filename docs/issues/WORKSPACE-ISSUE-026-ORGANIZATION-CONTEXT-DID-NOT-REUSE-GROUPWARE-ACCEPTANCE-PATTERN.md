# WORKSPACE-ISSUE-026 — Organization Context did not reuse the accepted Groupware acceptance pattern

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_RERUN_PENDING`

## Observed evidence

The actual Windows STEP005 run completed `18/23`. The Organization Context Example passed `8/8`, but the Connector→Example integration failed before producing a payload because the Connector-local script invoked literal `npm` and `node` through `subprocess`.

The Workspace had already solved this for Groupware:

```text
Workspace resolves node.exe and npm.cmd
→ prepare_invocation handles Windows .cmd
→ Workspace-owned E2E runner starts the Example
→ Connector and Example roots are explicit arguments
```

Organization Context copied the domain flow but created a second execution shape instead of reusing this accepted runner.

## Root cause

The implementation treated the Organization Context integration as a new harness problem even though the Groupware Workspace E2E was the accepted reference implementation.

## Correction

STEP005R1 adds `tests/run_organization_context_connector_example_e2e.py` as a domain adaptation of `tests/run_groupware_connector_example_e2e.py`. The Workspace runner owns Node/npm resolution and Windows `.cmd` invocation. The Connector remains independent and does not import Example source.

## Recurrence gate

- Workspace test asserts the Organization Context E2E imports `prepare_invocation` and `resolve_executable` from `workspace_process`.
- STEP005R1 acceptance asserts the Groupware Workspace E2E pattern is reused.
- Compatibility launcher delegates STEP005 to STEP005R1.
