# OR-ISSUE-018 — Python relocation omitted Product package-data resources

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

After Python modules were moved to the root package layout, the first real `create_app()` composition failed because the governance resolver could not find its constitution JSON. After that was corrected, application creation failed again because the Operations Console and Interactive Runner static assets remained under the removed source tree.

## Code-confirmed root cause

The initial relocation inventory enumerated only `*.py`. It did not treat Product-owned JSON, HTML, JavaScript, or CSS as files owned by their Python package. Static import validation therefore passed even though runtime resource resolution failed.

## Impact

The Service capabilities route, constitution runtime binding, Operations Console, and Interactive Runner could not start from the relocated tree or a Fresh ZIP.

## Fix

Ten non-Python files were moved with their canonical owners:

```text
governance JSON: 2
Operations Console assets: 4
Interactive Runner assets: 4
```

The executed relocation manifest records the original and target SHA-256 for every resource. All ten target files are byte-identical to STEP080A.

## Evidence

- `okcanvas_agent_runtime/core/governance/resources/`
- `okcanvas_agent_clients/dev_console/assets/`
- `okcanvas_agent_clients/dev_runner/assets/`
- `specs/architecture/STEP081_EXECUTED_RELOCATION_MANIFEST.json`
- executable `create_app()` route inventory in `scripts/validate_step081_architecture.py`

## Recurrence-prevention gate

`relocated_resources_byte_identical` compares each current target against the immutable baseline hash. `source_inventory_resources_exact` requires all ten resources, and the route inventory constructs the real FastAPI application.
