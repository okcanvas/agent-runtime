# WORKSPACE-ISSUE-043 — Assistant router lacked Tool-evidence Session focus

```text
Status: FIX_IMPLEMENTED_TEST_EXECUTION_DEFERRED_BY_USER
First fixed in Workspace: WORKSPACE_STEP008R4R8_RUNTIME_STEP092_SESSION_CONTEXTUAL_FOLLOW_UP_AND_STABLE_ENTITY_FOCUS
Runtime: STEP092_SESSION_CONTEXTUAL_FOLLOW_UP_AND_STABLE_ENTITY_FOCUS / 2.76.0
```

## Observed source defect

The Organization Assistant supported a bounded set of standalone short expressions and explicit prior-answer restatement, but the router only received `session_id`; it did not read a Product-owned stable entity/candidate reference produced by the previous Organization Context Tool result. `follow_up_state` existed in output models but was not a durable routing authority.

Consequences:

- `김민수 정보` could resolve correctly, while `그 사람 연락처는?` had no deterministic stable-ID continuation path;
- ambiguous results could not carry an evidence-bounded candidate set into the next routing decision;
- relying on SDK conversation history alone would leave entity reference resolution to model inference.

## Correction

STEP092 derives a bounded Session Context Focus from normalized allowlisted MCP Tool evidence, persists it as Session metadata, resolves only policy-bounded deictic/ellipsis/candidate follow-up, and validates GET result identity against the immutable routing hint. Multi-candidate references remain fail-closed.

## Recurrence guard

Source-prepared regression covers resolved follow-up, vague ambiguity, ordinal selection, evidence qualifier refinement, GET identity mismatch/cardinality, the shared 20-candidate display/focus bound, atomic successful commit, failed-turn preservation, last-committed-Turn invalidation, focus tamper and key-binding failure. Service/Admin preflight also snapshots one Session focus into one routing decision so the admitted stable hint cannot diverge from the returned route. Tests have not been executed because the user deferred all test execution until MinIO is prepared. The issue must not be marked CLOSED until those tests run.
