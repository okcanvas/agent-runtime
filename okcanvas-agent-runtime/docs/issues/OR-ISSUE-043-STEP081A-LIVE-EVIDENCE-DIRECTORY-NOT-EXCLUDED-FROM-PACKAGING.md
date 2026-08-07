# OR-ISSUE-043 — STEP081A local live evidence directory was not excluded from packaging

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_RERUN_PENDING
STEP: STEP081A_WINDOWS_NPM_COMMAND_RESOLUTION_AND_ACCEPTANCE_PORTABILITY
```

## Exact symptom

The STEP081A live runner writes mutable local Windows evidence under:

```text
docs/evidence/step081a-live/
```

The shared Product packaging policy excluded `docs/evidence/step081-live/` but did not exclude the new STEP081A directory. A developer who ran the live launcher before packaging could therefore create a ZIP whose contents depended on local credentials, runtime diagnostics, or machine-specific evidence.

## Code-confirmed root cause

`run_step081_live_acceptance.py` was revised to use the STEP081A live directory, while `scripts/step081_product_inventory.py::EXCLUDED_PREFIXES` and `.gitignore` retained only the STEP081 path. Launcher revision and packaging policy were updated independently.

## Impact

- Candidate ZIP contents could vary depending on whether a local STEP081A Windows run had occurred.
- Machine-local live evidence could be included in Product source packaging.
- Baseline-diff Compliance could count local runtime output as a Product change.
- Reproducible ZIP SHA and privacy boundaries could be lost.

No such directory was present in the current Linux work tree, so no local Windows evidence was packaged in the prior candidate. The defect was nevertheless executable and repeatable.

## Fix

1. Add `docs/evidence/step081a-live/` to the single Product inventory/packaging exclusion policy.
2. Add the same directory to `.gitignore`.
3. Extend the STEP081A repository contract test to require both exclusions.
4. Rebuild and inspect the candidate ZIP with a synthetic excluded directory present during packaging.

## Recurrence-prevention gates

- `tests/test_step081a_windows_npm_command_resolution_and_subprocess_portability.py`
- `scripts/step081_product_inventory.py::EXCLUDED_PREFIXES`
- STEP081A Fresh-ZIP forbidden-entry and deterministic-content validation
- Exact baseline-diff Compliance validation
