# OR-ISSUE-005 — STEP075D internal snapshot metadata escaped the immutable hash domain

## Status

`WINDOWS_FIX_ACCEPTED_DISTINCT_ANSWER_COMPLETENESS_FAILURE_REMAINS`

## Exact symptom

STEP075D Windows live acceptance passed readiness, one `gpt-4.1` model turn, Docker container creation, deterministic tar extraction and cleanup. The Sandbox Tool then emitted `SANDBOX_SELECTED_FILE_HASH_MISMATCH`; cleanup completed and orphan count was zero. The run passed 14/30 checks and preserved its acceptance workspace.

## Code-confirmed root cause

The Product built a canonical snapshot whose immutable entries were `README.md`, `UNTRUSTED.md` and `src/inventory.py`. It also wrote Product-owned metadata `.okcanvas-snapshot-manifest.json` into the staging root and included it in the tar inventory.

The evidence selector called `inspect_readonly_project(snapshot.staging_root, query)` without an allowed-file domain. The exact live request therefore selected both `src/inventory.py` and `.okcanvas-snapshot-manifest.json`. The latter is intentionally not a `SandboxSnapshotEntry`, so `entry_by_path.get(path)` returned no expected hash and the implementation reported the condition as a selected-file hash mismatch.

No project-file byte mismatch was established. The failure was a mismatch between the evidence candidate domain and the immutable snapshot-entry domain.

## Impact

A successful Docker materialization could fail deterministically whenever Product-owned staging metadata ranked as relevant evidence. The error code incorrectly conflated an out-of-domain selection with an actual byte-hash mismatch.

## Fix

1. Add an optional, validated `allowed_relative_paths` domain to the bounded read-only inspector.
2. For Sandbox execution, pass exactly the immutable `SandboxSnapshotEntry.path` set.
3. Keep the internal manifest in the tar inventory for Product verification, but exclude it from model-visible evidence selection and selected-file reads.
4. Fail closed with `SANDBOX_SELECTED_FILE_NOT_IN_SNAPSHOT` if any selected path escapes the immutable entry domain.
5. Reserve `SANDBOX_SELECTED_FILE_HASH_MISMATCH` for a selected in-domain file whose container bytes actually differ from the immutable snapshot hash.
6. Reproduce the exact Windows live query in deterministic recurrence tests.

## Automated recurrence prevention

- `tests/test_step075e_internal_snapshot_metadata_exclusion_and_hash_domain_fix.py`
- exact live-query reproduction against a real Product staging snapshot
- exact-domain subset assertion
- Product inspector assertion that it never `cat`s the internal manifest
- out-of-domain selection fail-closed error and cleanup/orphan assertions
- STEP075E deterministic acceptance
- STEP075E Windows live acceptance


## Windows closure note

STEP075E Windows live execution proved the metadata exclusion and immutable hash-domain fix: one project file selected, internal manifest absent, selected hashes verified, cleanup completed and orphan zero. The Run itself succeeded. A distinct final-answer completeness failure is tracked by OR-ISSUE-006.
