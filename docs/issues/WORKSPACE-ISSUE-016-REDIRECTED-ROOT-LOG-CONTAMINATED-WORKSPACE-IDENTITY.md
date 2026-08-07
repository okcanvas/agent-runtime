# WORKSPACE-ISSUE-016 — Redirected root log contaminated Workspace identity

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_RERUN_PENDING`

## Actual failure

The real Windows command was:

```cmd
sh_run_workspace_step003_acceptance > log.txt
```

Windows creates the redirected file before starting Python. STEP003R1 scanned the live Workspace root for manifest equality, but root-local acceptance output was not declared as non-source. The resulting unittest failure emitted an unbounded million-character dictionary diff instead of precise drift categories.

The same log also indicated `HANDOFF.md` was absent or different from the manifest. That tracked-file drift is not caused by redirection and must remain a failure.

## Root cause

Workspace identity distinguished environments, caches and mutable JSON evidence, but did not distinguish a root-local redirected acceptance log from packaged source.

## Correction

STEP003R2 excludes only these root-local acceptance outputs from identity and packaging:

```text
log.txt
*.log
```

Nested files such as `docs/architecture.log` are not excluded. Tracked files such as `HANDOFF.md` are never excused.

The integrated runner also emits bounded manifest diagnostics:

```json
{
  "missing": [],
  "changed": [],
  "unexpected": []
}
```

## Recurrence gates

- `log.txt` and root `*.log` must be excluded from Workspace identity and packages.
- Nested `.log` files must not be silently excluded.
- `HANDOFF.md` must remain tracked.
- Fresh ZIP acceptance must pass while stdout is redirected to a root log.
- Missing or changed tracked files must still fail `workspace_manifest_exact`.
