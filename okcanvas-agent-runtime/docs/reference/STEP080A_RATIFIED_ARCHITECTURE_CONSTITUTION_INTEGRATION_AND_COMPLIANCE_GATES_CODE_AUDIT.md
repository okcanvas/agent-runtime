# STEP080A_RATIFIED_ARCHITECTURE_CONSTITUTION_INTEGRATION_AND_COMPLIANCE_GATES — Code audit

## Audited baseline

- STEP080 final ZIP SHA-256: `53b3f6e5b96cc094922f8b45dc06f638a7be23893418ab3e68ca87ba81ebc2b2`
- External constitution ZIP SHA-256: `7cff27c684fc52eb56aa190442ea09e4bb0b2d6616de2fc862d253497428c21f`
- Constitution canonical SHA-256: `262b1db8549d7de5baf09307336b3ad5da07b7397f70cc2d6f5a1374eeb08bfa`

## Findings

1. STEP080 contained no `specs/architecture/constitution` path.
2. `RuntimeInfo` and `AgentRuntimeBinding` exposed capability topology but no governing architecture identity.
3. Service capabilities and `service-client-policy.json` exposed no constitution metadata.
4. No script validated the 18 pinned files, 127 clauses, 32 Gates, 36 coverage entries or 127 traceability entries.
5. No per-STEP record could prove that every changed file was mapped to a closed constitution clause.
6. The Windows entrypoint had no architecture-constitution acceptance command.

## Implemented boundary

The canonical human/machine bundle is stored unchanged under `specs/architecture/constitution/`. The runtime copy contains only the immutable constitution JSON and Gate catalog required for identity and fail-closed validation; equality with the canonical spec is tested. Runtime fingerprints bind the constitution snapshot and the SHA of validator implementation, not mutable external documentation paths.

## Behavior preservation

The source package remains under `src/okcanvas_agent_runtime`. Existing capability topology, Tool Search disabled state, Programmatic Tool Calling disabled state, model calls, Sandbox, Docker, ownership and event paths are unchanged. STEP080A only adds governance metadata and acceptance enforcement.

## Windows contract

`sh_run_step080a_live_acceptance.cmd` calls the registered `architecture-constitution-live-acceptance` command. It preserves the STEP080 62-check workflow and adds five constitution checks, so the final contract is exactly 67 checks.

## Validation-discovered implementation defect

The first executable Service capabilities regression raised `NameError` because the response referenced constitution fields without resolving the snapshot in `build_service_client_router()`. OR-ISSUE-016 records the exact failure. The router now resolves one immutable snapshot at composition time, and real FastAPI route tests prevent recurrence.

## Deterministic and fresh result

- Work-tree Acceptance: 37/37 PASS
- Focused regression: 49/49 PASS
- Historical capability regression: 31/31 PASS
- Full Python regression: 885/885 PASS across 223 files
- Fresh candidate Acceptance: 37/37 PASS
- Fresh candidate Python regression: 885/885 PASS
- Node: 14/14 PASS
- Reference integrity: 4/4 PASS
- npm pack: 23 files PASS
