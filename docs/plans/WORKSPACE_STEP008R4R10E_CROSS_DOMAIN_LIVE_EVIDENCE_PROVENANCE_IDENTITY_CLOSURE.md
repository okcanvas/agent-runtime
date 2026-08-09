# WORKSPACE STEP008R4R10E — Cross-domain Live evidence provenance identity closure

Workspace version: `0.8.4-r10e`  
Runtime: `STEP094R2_CROSS_DOMAIN_RUN_SUBMISSION_ADMISSION_OWNER_CLOSURE` / `2.78.2` (unchanged)

## Purpose

Prevent a mixed Workspace tree from producing a functionally passing Live result whose evidence identity does not identify the Runtime that actually executed.

## Canonical provenance fence

Before starting the functional cross-domain Turn sequence, the focused Live harness requires exact agreement among:

1. Workspace `current-baseline.json`,
2. Workspace `project-catalog.json`,
3. executable Runtime `core/baseline.py`,
4. Runtime `pyproject.toml` metadata.

After the local Runtime Service starts, `/v1/service/capabilities.runtime_version` must also equal the Workspace Runtime version. Evidence records hashes of the baseline/catalog/runtime baseline/pyproject/harness plus the Service-reported version.

Any mismatch is `FAILED`; the harness does not relabel, alias, infer, or fall back to another identity.

## Retained user evidence

The prior 19/19 Windows result is retained unchanged as functional proof but marked provenance-invalid for promotion because its CLI ran Runtime 2.78.2 while its footer claimed R10C / STEP094R1 / 2.78.1.

## Promotion

`NOT_READY` until a clean R10E focused Windows Live rerun returns a self-consistent provenance block and passes the functional cross-domain checks.
