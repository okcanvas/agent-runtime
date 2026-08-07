# STEP075E Code Audit

## Audited baseline

- STEP075D version `2.55.4`
- Windows live result: 14/30 failed after one model call and one started Sandbox Tool
- bounded Tool failure: `SANDBOX_SELECTED_FILE_HASH_MISMATCH`
- cleanup completed; orphan count zero

## Exact code defect

`build_readonly_snapshot` creates immutable `SandboxSnapshotEntry` rows for accepted project files and writes Product metadata `.okcanvas-snapshot-manifest.json` beside them in the staging root. The manifest is included in the deterministic tar and materialized inventory.

`ProductOwnedReadonlySandboxInspector.inspect` previously called:

```python
inspect_readonly_project(snapshot.staging_root, query_value)
```

The selector therefore ranked every bounded text file in staging, including Product metadata. It later looked up the selected path in `entry_by_path`; the manifest had no immutable entry and was collapsed into `SANDBOX_SELECTED_FILE_HASH_MISMATCH`.

The exact STEP075D fixture and live query reproduced `('src/inventory.py', '.okcanvas-snapshot-manifest.json')` while immutable entries were only `README.md`, `UNTRUSTED.md`, and `src/inventory.py`.

## Implementation

`inspect_readonly_project` now accepts optional keyword-only `allowed_relative_paths`. The domain is normalized to safe canonical POSIX-relative paths and rejects empty, absolute, parent-escaping or non-canonical values.

The Sandbox inspector constructs `entry_by_path` first and calls the selector with:

```python
allowed_relative_paths=entry_by_path.keys()
```

The internal manifest remains in the tar and exact materialized inventory, but cannot enter model-visible evidence selection.

A second fail-closed guard checks every selected path before any container `cat` command. A missing entry raises:

```text
SANDBOX_SELECTED_FILE_NOT_IN_SNAPSHOT
```

Only a selected in-domain file whose container bytes hash differently raises:

```text
SANDBOX_SELECTED_FILE_HASH_MISMATCH
```

## Security review

Unchanged:

- already-local immutable image digest;
- runtime pull disabled;
- network none, no ports, no mounts, no secrets;
- read-only root filesystem, cap-drop ALL, no-new-privileges;
- root-owned noexec/nosuid/nodev tmpfs;
- fixed root tar extractor only;
- model-visible fixed non-root `find/cat/grep/tail` commands;
- bounded output, forced cleanup, orphan reconciliation;
- raw source, paths, image and secrets excluded from persisted Tool evidence.

The change narrows the readable evidence domain and does not add capability.

## Recurrence gates

`tests/test_step075e_internal_snapshot_metadata_exclusion_and_hash_domain_fix.py` verifies:

- the historical unrestricted live-query reproduction;
- the fixed exact-domain selection;
- the manifest is never `cat`-read;
- out-of-domain selection uses its distinct stable code;
- cleanup and orphan-zero still occur;
- unsafe allowed-domain paths are rejected.
