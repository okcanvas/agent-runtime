# WORKSPACE-ISSUE-070 — Grounded delegation must bound specialist requests, not only admissions

Status: FIXED_IN_STEP096B

## Failure

The first max-one fence counted only successfully admitted children. After an admission denial the
model could potentially request the other specialist, turning denial into an implicit fallback path.

## Correction

The Root gateway now maintains `grounded_agent_tool_request_count` separately from admitted child
count. At most one specialist request is accepted per Turn, whether it is admitted or denied. The
policy and Product marker both declare one request and one child call maximum.

## Recurrence gate

A denied governed delegation never authorizes a second specialist attempt in the same Turn.
