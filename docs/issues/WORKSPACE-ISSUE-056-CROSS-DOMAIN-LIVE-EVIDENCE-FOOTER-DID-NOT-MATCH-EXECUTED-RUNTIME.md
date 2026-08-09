# WORKSPACE-ISSUE-056 — Cross-domain Live evidence footer did not match executed Runtime

## Actual Windows evidence

The user-reported focused cross-domain Live run functionally passed 19/19. Its CLI transcript executed `Runtime 2.78.2` and all three Runs succeeded, but the same evidence footer recorded Workspace R10C / Runtime STEP094R1 / 2.78.1.

This is not a Product cross-domain failure. It is an evidence provenance failure caused by a mixed Workspace tree being able to execute without proving that the Workspace current baseline and the executable Runtime identity were the same release.

## Root defect

The focused Live harness trusted `specs/workspace/current-baseline.json` for evidence labels and did not cross-check that label against:

- `specs/workspace/project-catalog.json`,
- `okcanvas_agent_runtime.core.baseline`,
- Runtime `pyproject.toml`, or
- the started Service `/v1/service/capabilities` runtime version.

Therefore a mixed tree could produce functionally correct Live behavior with a stale evidence footer.

## Corrective ownership

R10E keeps Runtime STEP094R2 / 2.78.2 unchanged. The Workspace Live harness now records hashes and independent identity values and fails closed before the functional Turn sequence when the local identity sources diverge. After the Service starts, it also requires the Service runtime version to equal the Workspace baseline runtime version.

## Explicit non-fixes

No helper alias, version alias, fallback, compatibility shim, evidence relabeling, historical evidence rewrite, Session switching, Tool substitution, or Product behavior weakening is allowed.

The prior 19/19 evidence remains retained as `FUNCTIONAL_PASS_PROVENANCE_INVALID`; it is not rewritten into R10D/R10E promotion evidence.
