# WORKSPACE-ISSUE-061 — Historical Routing Regression Fixtures Lag Current Session Runtime Contract

## Status

RECORDED_CURRENT_GATE_USES_CURRENT_FOCUSED_MATRIX

## STEP

STEP096A

## Observation

Historical routing fixtures retain old STEP/version/session-root assumptions and one partial fake SessionRuntime omits the formal focus method.

## Correction / recurrence gate

Do not relax Product contracts for stale fixtures; current STEP acceptance owns an explicit focused matrix and historical debt stays visible.
