# Evaluation specifications

Immutable deterministic case manifests. A model is never the sole pass/fail judge.

STEP026 adds deterministic Evaluation cases for covered, tie-ordering, and single-shortage replenishment outputs.

## STEP048 case

`sqlite-session-native-guardrail-v1` evaluates the later successful continuity Turn after both INPUT and OUTPUT tripwire rollback cases. Rejected Turns create no Evaluation.
