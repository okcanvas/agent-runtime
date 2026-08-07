# CLI-ISSUE-005 — Windows Node executable path was split by shell execution

## Failure

The CLI acceptance runner used `shell: true` so a Node executable under `C:\Program Files\...` was parsed as `C:\Program`. Windows acceptance failed before tests ran.

## Correction

The runner enumerates `*.test.mjs` files itself and invokes `process.execPath` with an argument array and `shell: false`.

## Recurrence gate

A CLI test rejects shell-based Node execution and wildcard test arguments.
