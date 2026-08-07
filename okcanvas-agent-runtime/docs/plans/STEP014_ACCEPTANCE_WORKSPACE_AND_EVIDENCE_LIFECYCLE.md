# STEP014 — Acceptance Workspace and Evidence Lifecycle

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_PENDING`

## Goal

Replace ad-hoc deterministic acceptance `TemporaryDirectory` handling with one project-owned workspace lifecycle. This is acceptance infrastructure, not Product Task/Run state.

## Contract

1. Create one isolated workspace per acceptance ID below the OS temp root or `OKCANVAS_ACCEPTANCE_WORK_ROOT`.
2. Keep acceptance databases, artifacts, scratch data, and staged evidence in separate subdirectories.
3. Close registered resources in reverse registration order.
4. Export compact evidence outside the workspace before cleanup.
5. On PASS, delete the workspace using bounded retries only after explicit close.
6. On FAIL or exception, preserve the workspace and report its exact path.
7. Cleanup failure converts a previously passed acceptance to failed and preserves the workspace.
8. Workspace manifests declare `product_runtime_state=false`.

## Migrated deterministic acceptance scripts

- STEP005 Core Store verifier;
- STEP006–STEP013 deterministic acceptance scripts.

STEP002–STEP004 live Codex acceptance remains on its existing sensitive evidence and controlled workspace contracts. It is not silently reclassified by this STEP.

## Reference use

- ADAPT `reference/upstream/openai-agents-python-0.19.0/src/agents/sandbox/sandboxes/unix_local.py`: explicit caller/runtime workspace ownership and cleanup only after prerequisite release.
- ADAPT `reference/upstream/openai-agents-python-0.19.0/src/agents/mcp/manager.py`: reverse-order resource cleanup and cleanup state removal in `finally` boundaries.
- REJECT best-effort deletion that swallows cleanup errors as acceptance success. OKCanvas preserves the workspace and fails closed.
- REJECT direct `/reference` import.

## Non-scope

- Product runtime database placement;
- background/distributed execution;
- Codex live-workspace contract migration;
- artifact object storage;
- release promotion gates.
