# OR-ISSUE-015 — Architecture constitution existed outside the Product package and was not enforced

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING
STEP: STEP080A_RATIFIED_ARCHITECTURE_CONSTITUTION_INTEGRATION_AND_COMPLIANCE_GATES
```

## Exact symptom

The ratified Client/Transport/Agent architecture constitution existed only as a separate handoff ZIP under `/mnt/data`. The STEP080 Product ZIP did not contain the constitution bundle, did not expose its identity through Runtime metadata, did not bind it into Agent runtime fingerprints, and had no executable validator that could fail a future STEP when a clause, mandatory Gate, changed file, traceability entry, or annex was omitted.

## Code-confirmed root cause

STEP080 normalized Agent capabilities, but its packaging and acceptance contracts only knew capability topology and SDK example inventory. No Product-owned governance package, constitution resource, bundle validator, STEP compliance contract, Service capability fields, RuntimeInfo fields, runtime-binding SHA, Windows command, or recurrence test existed.

## Impact

A future directory migration could claim compliance while omitting one of the 127 clauses, 32 mandatory Gates, 36 audit coverage items, 9 source inventories, or a changed file. A ZIP-only handoff could also lose the governing source material without Product acceptance detecting it.

## Fix

- package the complete 18-file normative bundle under `specs/architecture/constitution/`;
- package an exact runtime manifest and Gate catalog under `okcanvas_agent_runtime.governance.resources`;
- add immutable constitution and STEP compliance validators;
- bind constitution identity into RuntimeInfo, AgentRuntimeBinding, Service capabilities and service policy;
- require a machine-readable per-STEP compliance record with closed clauses, changed-file coverage and Gate outcomes;
- add deterministic and Windows live acceptance commands;
- preserve the STEP080 capability runtime unchanged and keep physical source movement blocked.

## Recurrence-prevention gates

- `tests/test_step080a_architecture_constitution_and_compliance_gates.py`
- `tests/test_step080a_windows_entrypoint_architecture_constitution_registration.py`
- `scripts/validate_architecture_constitution.py`
- `scripts/run_step080a_acceptance.py`
- `scripts/run_step080a_live_acceptance.py`
- `GATE-CONSTITUTION-BUNDLE-COMPLETE`
- `GATE-CLAUSE-COVERAGE-100`
- `GATE-TRACEABILITY-COMPLETE`
- `GATE-LAUNCHER-REGISTRY-COMPLETE`

## Non-change proof

No Python package path, REST/SSE route, Product Event truth, model, Tool, Skill, MCP, sub-Agent, Docker, Sandbox, ownership, persistence, secret or workspace behavior is activated or moved in this corrective governance revision.

## Implementation defect discovered during closure

The first executable Service capability regression exposed OR-ISSUE-016, where the route referenced constitution fields without resolving the snapshot. That defect is separately recorded and recurrence-gated.
