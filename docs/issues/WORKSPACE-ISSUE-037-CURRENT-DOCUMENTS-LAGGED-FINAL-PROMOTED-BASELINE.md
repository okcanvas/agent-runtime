# WORKSPACE-ISSUE-037 — Current documents lagged the final promoted baseline

## State

```text
LOCAL_AND_FRESH_DETERMINISTIC_ACCEPTED
```

## Evidence

The root final approval and Promotion Marker were current, while the root README and nested Runtime
README/HANDOFF still described STEP008R2, STEP090 or pending Windows Live execution.

## Risk

A new conversation using only the ZIP could select an obsolete baseline or repeat already-closed
Live work.

## Closure

STEP008R4R1 separates historical evidence from current status documents, aligns all current README
and HANDOFF files, records the Product master plan, and adds exact document-alignment tests.
