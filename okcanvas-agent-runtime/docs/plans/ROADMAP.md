# Roadmap

## Current baseline

- Version `2.60.1`
- `STEP080A_RATIFIED_ARCHITECTURE_CONSTITUTION_INTEGRATION_AND_COMPLIANCE_GATES`
- `IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

## Accepted predecessor

STEP079A is deterministic accepted 29/29 and Windows-live accepted 57/57. STEP080 capability topology is the source baseline for this corrective governance revision and remains behaviorally preserved.

## STEP080A selected problem

The complete ratified architecture constitution existed only outside the Product package. It was not runtime-identifiable and could not fail a future STEP for an omitted clause, mandatory Gate, changed file, traceability entry, source audit or annex hash.

## STEP080A scope

- package the immutable 18-file constitution bundle;
- expose an immutable runtime constitution snapshot;
- validate 127 clauses, 32 mandatory Gates, 36 audit coverage entries, 127 traceability records, 12 annex records and 9 source inventories;
- require per-STEP changed-file/Clause/Gate compliance records;
- bind the constitution into Agent runtime fingerprints and authenticated Service capabilities;
- register deterministic and Windows live acceptance commands;
- keep `src/okcanvas_agent_runtime` physically unchanged.

## Current gate

```text
UNSELECTED_PENDING_STEP080A_WINDOWS_LIVE_ACCEPTANCE
```

## Historical accepted foundations

- STEP068 bounded local PDF/PNG/JPEG input is Windows-live accepted.
- Hosted File Search remains post-MVP.
- Current agents may consume bounded document input without introducing vector-store lifecycle.
- `STEP070_PRODUCT_OWNED_SKILL_PACKAGE_FOUNDATION_V1` and the Product-owned Skill contract remain preserved.

## Preserved capability foundation

- Agent topologies: 27
- Active bindings: 33
- Capability families: 8
- SDK example inventory: 30
- Tool Search runtime: disabled
- Programmatic Tool Calling runtime: disabled
- Product Skill executable code and Shell: disabled

## Source-layout migration gate

The ratified constitution requires the final root package `okcanvas_agent_runtime/`, but physical migration is blocked in this revision. STEP081 may be selected only after STEP080A Windows live acceptance and must use the compliance record, migration map and mandatory Gate catalog.

## Non-goals

No package movement, REST/SSE/WebSocket refactor, Client implementation, Tool activation, Shell, Apply Patch, Code Interpreter, File Search, new model call or authority expansion.
