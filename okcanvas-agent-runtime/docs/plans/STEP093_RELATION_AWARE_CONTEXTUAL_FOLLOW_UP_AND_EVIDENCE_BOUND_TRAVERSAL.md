# STEP093 — Relation-aware contextual follow-up and evidence-bound traversal

```text
Runtime: STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL
Version: 2.77.0
Parent: STEP092 / 2.76.0
State: IMPLEMENTED_STATIC_VALIDATION_ONLY_TEST_EXECUTION_DEFERRED_BY_USER_MINIO_PENDING
Promotion: NOT_READY
```

## Goal

Extend stable Session Context Focus from “same entity, another field” to explicitly represented Organization Context relationships without making the model a graph authority.

## Contract

1. Relation intent is matched only by the versioned Product policy.
2. The source entity must come from current, non-stale STEP092 Tool-evidence focus.
3. Multi-source focus never guesses; ordinal/qualifier selection stays within prior Tool evidence.
4. Routing creates immutable GET source ID/type plus relation type/direction/target-type hint.
5. `get_organization_entity` Tool evidence must exactly match the source stable ID/type.
6. Relationship evidence must prove completeness.
7. Only exact matching relation rows can be projected.
8. Projected stable target entities become next Session focus; multiple targets remain `MULTIPLE`.
9. Model prose, arbitrary relation names and implicit inverse traversal are not evidence.

## Bounded relation policy

Current policy covers only relation types present in the published Organization Context dataset/contract. Reverse traversal is allowed only where explicitly registered (`CLIENT_USES_PRODUCT` and `PROJECT_FOR_CLIENT`). Maximum projected result count is 20.

## Cross-project strengthening

Connector STEP003 / 0.3.0 validates GET relation completeness metadata. Example STEP003 / 0.3.0 publishes that metadata around its existing 100-row detailed relation bound.

## Validation state

Test sources are prepared but not executed. Static/source/package checks are permitted while the user's MinIO test hold remains active. No parent pass count is promoted as STEP093 evidence.

## Prepared focused Live gate

The Workspace packages a dedicated relation-chain Live harness for the three-turn `employee -> managed products -> selected product clients` conversation. The source is prepared but unexecuted; STEP093 remains TEST_PENDING until the deferred executable gates run.
