# WORKSPACE-ISSUE-020 — Windows Live temporary cleanup preceded process shutdown

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

## Observed Windows evidence

The user's actual STEP004 Live payload loaded `.env.local`, proved both `OPENAI_API_KEY` and `OKCANVAS_AGENT_MODEL`, recorded model `gpt-4.1`, and then failed with built-in `PermissionError`. The payload classified that exception as `OPENAI_AUTHENTICATION_OR_PERMISSION`.

## Code root cause

`run_workspace_step004_live_acceptance.py` placed `tempfile.TemporaryDirectory(...)` inside an outer `try/finally`. Python exited the temporary-directory context before entering the outer `finally`, while the Runtime ASGI thread, Connector ASGI thread, Node process, SQLite files and process pipes were still open. On Windows, temporary-tree deletion can therefore raise `PermissionError` before the shutdown code runs.

The classifier also treated every exception type containing `permission` as OpenAI authentication/permission, including built-in filesystem `PermissionError`. This allowed a harness cleanup defect to be reported as a Provider authentication defect.

## Correction

STEP004R1:

1. uses an explicit temporary directory rather than a context that deletes before the outer `finally`;
2. stops Runtime and Connector ASGI servers first;
3. terminates and waits for the Node process, then closes stdout/stderr pipes;
4. removes the temporary tree only after all process boundaries are closed, with bounded Windows retry;
5. records `failure_stage`, `harness_cleanup_completed`, cleanup error types and transient removal error types;
6. classifies built-in `PermissionError` as `HARNESS_FILESYSTEM_PERMISSION`;
7. restricts `OPENAI_AUTHENTICATION_OR_PERMISSION` to OpenAI/Agents exception modules;
8. prevents cleanup failure from overwriting the original execution failure.

## Recurrence gates

- Unit test proves built-in `PermissionError` is not classified as OpenAI authentication.
- Unit test injects a permission failure and proves the original category survives successful cleanup.
- Source-order test proves server/process shutdown precedes temporary-tree removal.
- Unit test proves transient Windows removal locks are retried and recorded safely.
- API keys and raw Provider errors remain absent from persisted evidence.
