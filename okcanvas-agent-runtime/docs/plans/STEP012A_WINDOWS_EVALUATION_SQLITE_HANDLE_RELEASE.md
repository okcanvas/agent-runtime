# STEP012A — Windows Evaluation SQLite Handle Release

## Objective

Correct the Windows-only STEP012 acceptance cleanup failure caused by Evaluation SQLite connections relying on garbage collection instead of explicit file-handle release.

## Observed evidence

Windows `sh_run_step012_acceptance.cmd` completed the functional evaluation flow but failed while deleting the temporary directory with `WinError 32` on `evaluation.sqlite3`.

## Inspected Reference

- `reference/CODE_MAP.md` and `reference/MANIFEST.json`;
- `reference/upstream/openai-agents-python-0.19.0/src/agents/memory/sqlite_session.py`.

## Reference decision

- **ADAPT** the upstream SQLite session's explicit connection ownership and `close()` lifecycle.
- **REJECT** direct import or reuse of the SDK Session implementation because Evaluation Store is product state, not Agent conversation memory.

## Root cause

`sqlite3.Connection` used as a context manager commits or rolls back but does not itself define the product's handle-release boundary. The Evaluation Store relied on object destruction after method return. That was not deterministic enough for Windows temporary-directory deletion.

## Change

- add an operation-scoped `_connection()` context manager;
- commit on normal completion;
- rollback on failure;
- always call `close()` in `finally`;
- route initialize, save, get, and list operations through that boundary;
- add a regression test that tracks every opened connection and proves all are explicitly closed.

## Non-scope

- schema changes;
- connection pooling;
- long-lived Evaluation Store connections;
- cleanup-error suppression;
- `gc.collect()` as a correctness mechanism;
- direct `/reference` import.

## Acceptance

- existing STEP012 16/16 acceptance passes;
- all Evaluation Store operation connections report explicit close;
- full test suite passes;
- immutable Reference verification passes;
- Windows rerun must remove the acceptance temporary database without `WinError 32`; this remains the final live acceptance check.
