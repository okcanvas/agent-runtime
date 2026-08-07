# STEP080A_RATIFIED_ARCHITECTURE_CONSTITUTION_INTEGRATION_AND_COMPLIANCE_GATES

## Identity

```text
version: 2.60.1
source baseline: STEP080_PRODUCT_OWNED_CAPABILITY_TOPOLOGY_AND_TOOL_DISCOVERY_FOUNDATION / 2.60.0
constitution: 262b1db8549d7de5baf09307336b3ad5da07b7397f70cc2d6f5a1374eeb08bfa
state: IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING
```

## Applied constitution clauses

```text
GOV-004 GOV-005 GOV-006 GOV-007 GOV-008 GOV-009 GOV-010
ARC-001 ARC-004 ARC-005
CMP-006
HIS-001 HIS-002 HIS-004
TST-003 TST-004 TST-005 TST-006
MIG-001 MIG-002 MIG-008 MIG-009
```

## Selected problem

The architecture constitution was complete as an external document bundle but was not part of the Product ZIP and could not fail a STEP for omitted clauses, Gates, changed files, traceability or annex evidence.

## Scope

1. Integrate the full ratified bundle without modifying its bytes.
2. Add runtime-readable immutable constitution identity.
3. Add fail-closed bundle and STEP compliance validators.
4. Bind constitution identity into RuntimeInfo, Agent runtime fingerprints and authenticated Service capability metadata.
5. Add deterministic/Windows launchers and recurrence tests.
6. Record every changed file in the STEP compliance record.

## Explicit non-scope

- no `src/okcanvas_agent_runtime` relocation;
- no Client, REST, SSE or WebSocket refactor;
- no domain/application/adapter package movement;
- no Tool Search or Programmatic Tool Calling activation;
- no model, Tool, MCP, Skill, sub-Agent or persistence authority change.

## Completion conditions

- 127 unique clauses and 32 mandatory Gate IDs validate;
- all 18 bundle inventory files match their pinned SHA-256;
- all 36 audit coverage entries remain covered with zero uncovered items;
- all 127 traceability entries remain present;
- the STEP compliance record has zero open clauses, unregistered files or unexecuted required Gates;
- runtime and Service metadata expose the exact constitution SHA;
- STEP080 capability regression remains unchanged;
- Windows live runs the accepted STEP080 workflow and adds five constitution checks for a final total of 67.

## Deterministic result

```text
Acceptance: 37/37 PASS
Constitution validator: 16/16 PASS
Compliance validator: 8/8 PASS
Launcher registry: 6/6 PASS
Focused regression: 49/49 PASS
Historical capability regression: 31/31 PASS
Full Python regression: 885/885 PASS across 223 files
Fresh candidate regression: 885/885 PASS
Node: 14/14 PASS
Reference: 4/4 PASS
npm pack: 23 files PASS
```
