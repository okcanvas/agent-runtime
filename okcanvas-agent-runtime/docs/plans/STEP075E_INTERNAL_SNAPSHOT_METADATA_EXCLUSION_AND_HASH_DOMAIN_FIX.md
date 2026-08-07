# STEP075E — Internal Snapshot Metadata Exclusion and Hash Domain Fix

## Identity

- Step: `STEP075E_INTERNAL_SNAPSHOT_METADATA_EXCLUSION_AND_HASH_DOMAIN_FIX`
- Version: `2.55.5`
- State: `IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

## Trigger

STEP075D Windows live acceptance reached the real Docker tmpfs workspace, deterministic tar extraction and container file reads. It then failed with `SANDBOX_SELECTED_FILE_HASH_MISMATCH`, cleanup completed, and orphan count was zero.

The exact live fixture was reproduced locally. Immutable snapshot entries were:

- `README.md`
- `UNTRUSTED.md`
- `src/inventory.py`

The unconstrained evidence selector returned:

- `src/inventory.py`
- `.okcanvas-snapshot-manifest.json`

The manifest is Product-owned staging metadata and intentionally has no `SandboxSnapshotEntry`. The implementation therefore treated a candidate-domain escape as a byte-hash mismatch.

## Selected scope

1. Add an optional validated `allowed_relative_paths` domain to `inspect_readonly_project`.
2. Bind Sandbox evidence selection to exactly the immutable snapshot-entry paths.
3. Keep `.okcanvas-snapshot-manifest.json` in the Product tar/materialization inventory, but never expose it as project evidence or read it with the model-visible `cat` path.
4. Add `SANDBOX_SELECTED_FILE_NOT_IN_SNAPSHOT` for fail-closed domain escape.
5. Reserve `SANDBOX_SELECTED_FILE_HASH_MISMATCH` for an in-domain file whose container bytes differ from its immutable snapshot hash.
6. Reproduce the exact STEP075D live request in deterministic regression tests.
7. Record the repeatable failure as OR-ISSUE-005.

## Explicit non-scope

- no Shell, Apply Patch, dependency installation or arbitrary executable;
- no network, ports, host bind, remote mount or Docker socket;
- no image pull, resume or snapshot restore;
- no provider/policy capability expansion;
- no change to deterministic GNU tar, fixed root extractor or non-root read commands;
- no Skill change;
- no STEP076 selection.

## Acceptance gates

- exact live request selects only `src/inventory.py` from the canonical staging snapshot;
- every selected path is a member of immutable snapshot entries;
- internal manifest remains materialized but is never selected or `cat`-read;
- a forced out-of-domain selection fails with `SANDBOX_SELECTED_FILE_NOT_IN_SNAPSHOT` and still completes cleanup with orphan zero;
- in-domain byte mismatch remains `SANDBOX_SELECTED_FILE_HASH_MISMATCH`;
- focused, historical, full Python, Node, Reference and packaging validations pass;
- Windows live rerun succeeds before STEP076 selection.
