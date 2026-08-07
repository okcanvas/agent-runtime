# WORKSPACE-ISSUE-021 — Workspace launchers bypassed Python bytecode isolation

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_RERUN_PENDING`

## Observed Windows evidence

The user's STEP004 deterministic readiness payload passed Workspace identity and Runtime retained evidence but failed the actual Main Assistant E2E while resolving `groupware-read-agent`:

```text
AgentDefinitionContractError:
Groupware read Sub-agent must retain the exact internal read-only contract
```

The checked source definition contained STEP087R1's `max_turns=2`, and the Workspace manifest was exact. This source/Runtime contradiction is possible when a prior in-tree timestamp-valid `.pyc` remains after a ZIP is overlaid onto an existing directory.

## Missing boundary

The Runtime project already had `scripts/python_bytecode_isolation.py` and required `PYTHONPYCACHEPREFIX` before child-interpreter startup. STEP004 Workspace launchers invoked the Runtime interpreter directly and did not establish a Workspace-scoped bytecode overlay. Existing in-tree `__pycache__` could therefore be read even though caches were excluded from the ZIP and manifest.

## Correction

STEP004R1 adds `scripts/workspace_python_bytecode_isolation.py`. Both deterministic and Live Workspace launchers now start a child interpreter with a process-owned `PYTHONPYCACHEPREFIX` outside the Workspace. The setting is inherited by Runtime, Connector and all nested Python subprocesses. Compatibility STEP004 launchers delegate to STEP004R1.

## Recurrence gates

- A synthetic timestamp-valid stale in-tree `.pyc` returns the old value without isolation.
- The same source returns the current value under the Workspace overlay.
- Both STEP004R1 Windows launchers must invoke the Workspace bytecode-isolation wrapper.
- Deterministic Main Assistant E2E must pass 14/14 inside the isolated execution tree.
- Workspace identity continues to exclude all `__pycache__` paths.

The exact user-machine stale file is not persisted in the log, so this document records the reproducible missing boundary and observed compatible failure mechanism rather than asserting a recovered file path.
