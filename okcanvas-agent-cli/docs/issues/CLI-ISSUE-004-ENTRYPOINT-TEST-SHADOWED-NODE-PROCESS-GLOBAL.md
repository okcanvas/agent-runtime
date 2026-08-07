# CLI-ISSUE-004 — Entrypoint test shadowed the Node process global

## Failure

The first CLI entrypoint regression declared `const process = spawnSync(process.execPath, ...)`.
The local binding entered the temporal dead zone before the right-hand side evaluated, so the test failed
with `ReferenceError: Cannot access 'process' before initialization`.

## Correction

Child-process results use names such as `child` or `processResult`; the Node `process` global is never reused
as a local binding in CLI tests.

## Recurrence gate

The CLI help and missing-Bearer entrypoint tests execute through `process.execPath` on every acceptance run.
