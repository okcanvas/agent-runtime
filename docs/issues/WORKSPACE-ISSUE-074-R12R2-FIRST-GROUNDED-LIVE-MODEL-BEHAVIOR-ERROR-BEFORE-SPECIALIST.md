# WORKSPACE-ISSUE-074 — R12R2 first grounded Live failed before specialist request

## Status
RECORDED_ROOT_CAUSE_NOT_YET_CLASSIFIED_R12R3_DIAGNOSTIC_READY

## Observed evidence
The user-reported Windows R12R2 run reached `model.completed` on the first scenario and then emitted
`agent.failed` / `run.failed` with `detail_type=ModelBehaviorError`. There were zero
`agent.tool.requested`, zero admitted child requests, and zero execution MCP Tool calls.

## What this proves
The failure is before specialist execution. It does **not** prove a child Agent, lazy MCP connection,
Organization Context MCP, Groupware MCP, or Product normalizer defect.

## What is still unknown
R12R2 did not preserve enough safe classification data to distinguish among structured final-output
validation failure, unknown Tool call, malformed Tool arguments, or structured Tool argument schema
validation failure.

## Rule
Do not change routing semantics, Agent instructions, MCP contracts, or admission rules until the exact
ModelBehaviorError category is observed from a content-free diagnostic rerun.
