# WORKSPACE_STEP003R2_WINDOWS_PROJECT_PYTHON_ENVIRONMENT_AND_REDIRECTED_LOG_IDENTITY_CLOSURE

## Objective

Close the three independent defects proven by the user's real Windows STEP003R1 log without changing STEP003 product behavior:

1. Select each Python project's own `.venv` interpreter.
2. Keep root redirected acceptance logs outside Workspace source identity.
3. Record real Windows execution and acceptance truthfully.

## Non-goals

- No Runtime product source change.
- No CLI product source change.
- No Connector product source change.
- No Example product source change.
- No API, route, Session, routing, MCP, delegated identity or E2E semantic change.
- No live OpenAI model or real enterprise Groupware claim.

## Implementation

- Add shared `resolve_project_python` with dependency probing and fail-closed setup guidance.
- Run Connector retained acceptance and Connector E2E with Connector `.venv`.
- Run Main Assistant full E2E with Runtime `.venv`.
- Retain bootstrap Python only for Workspace orchestration and dependency-free Workspace unit tests.
- Exclude root `log.txt` and root `*.log` from identity/package; retain all nested logs and tracked documents.
- Add bounded manifest drift evidence.
- Add STEP003R2 launcher and make STEP003/STEP003R1 compatibility launchers delegate to it.
- Derive Windows execution and acceptance flags from the current run.

## Acceptance

- Workspace unit tests pass.
- Connector retained acceptance 7/7 passes under Connector Python.
- Connector -> Example 7/7 passes under Connector Python.
- Main Assistant E2E 14/14 passes under Runtime Python.
- Redirected CP949 aggregate JSON remains valid.
- A root `log.txt` does not alter manifest or package identity.
- Missing/changed `HANDOFF.md` still fails.
- Fresh package and deterministic repack are byte-identical.

## Windows continuation

Use a fresh extraction. Because `.venv` and `node_modules` are intentionally excluded from the ZIP, run:

```cmd
sh_setup_workspace.cmd
sh_run_workspace_step003r2_acceptance.cmd > log.txt
```

Promote only if the final payload is `PASSED` and reports `windows_step003r2_executed: true` and `windows_step003r2_accepted: true`.
