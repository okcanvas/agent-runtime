# WORKSPACE STEP008R4R9 — Runtime STEP093 relation-aware contextual follow-up

```text
Workspace: WORKSPACE_STEP008R4R9_RUNTIME_STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL
Version: 0.8.4-r9
Runtime: STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL
Runtime Version: 2.77.0
Parent Workspace: STEP008R4R8 / 0.8.4-r8
Parent ZIP SHA-256: 31e288d94a0ec5b10d3a6ab24ddb46979f060d6eb2bbd1b2ac50dac22c1d48f1
State: IMPLEMENTED_STATIC_VALIDATION_ONLY_TEST_EXECUTION_DEFERRED_BY_USER_MINIO_PENDING
Promotion: NOT_READY
```

## Workspace closure

This Workspace step composes Runtime STEP093 with Organization Context Connector STEP003 and Example STEP003. The new cross-project contract is relationship completeness: detailed entity GET evidence must expose total/returned/truncated relationship metadata, the Connector validates it, and Runtime refuses incomplete evidence for deterministic relation traversal.

No test gate was executed. Current Workspace/Runtime/Connector/Example acceptance sources are prepared for later execution only.

## Historical evidence

All existing `docs/evidence` artifacts keep their original Step identity and bytes. Historical STEP091B3R1 PostgreSQL 15-table/19-of-19 live evidence is not rewritten; the current topology remains 16 tables because STEP092 added Session Context Focus and STEP093 adds no table.

## Prepared focused Live gate

A dedicated future Windows Live source is packaged at `scripts/run_workspace_step008r4r9_relation_live_acceptance.py` with launcher `sh_run_workspace_step008r4r9_relation_live_acceptance.cmd`. It executes three sequential turns in one Session: `김선임 연락처` -> `그 사람이 담당하는 제품은?` -> `첫 번째 제품 고객사는?`. It validates sequential routing after each prior Turn commit, exact MCP Tool order, relation projection focus transitions, and Connector request paths. It remains **source-prepared only** and is not acceptance evidence until actually executed after the user lifts the test hold.
