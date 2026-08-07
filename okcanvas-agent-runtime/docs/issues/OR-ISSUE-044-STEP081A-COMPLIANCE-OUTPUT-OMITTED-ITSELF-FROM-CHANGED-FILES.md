# OR-ISSUE-044 — STEP081A Compliance output omitted itself from changed files

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_RERUN_PENDING
STEP: STEP081A_WINDOWS_NPM_COMMAND_RESOLUTION_AND_ACCEPTANCE_PORTABILITY
```

## Exact symptom

The first STEP081A Compliance generation reported 1,166 changed files, but immediate validation reported 1,167 and failed `changed_files_exact`:

```text
unregistered_changed_files:
- docs/evidence/STEP081A_CONSTITUTION_COMPLIANCE.json
```

## Code-confirmed root cause

`generate_step081_compliance.py` calculated the current Product file map before writing its output. Because the STEP081A Compliance path did not exist in the STEP080A baseline or in the current tree at calculation time, the generator could not discover the file that it was about to create.

## Impact

- A first-time corrective revision could not produce a self-consistent Compliance record.
- Re-running the generator happened to include the now-existing file, hiding an order-dependent defect.
- Clean Fresh extraction and another conversation could observe different results from an already-used work tree.

## Fix

When the configured Compliance output is inside the Product root, the generator explicitly registers that relative path in `changed_files` before writing the record. The exact changed-file validator still recomputes the full post-write tree and rejects every other omission or stale declaration.

## Recurrence-prevention gates

- `tests/test_step081_root_package_and_architecture_restructuring.py`
- first-run generation followed immediately by `scripts/validate_step081_compliance.py`
- STEP081A Fresh-ZIP Compliance and integrated Acceptance
