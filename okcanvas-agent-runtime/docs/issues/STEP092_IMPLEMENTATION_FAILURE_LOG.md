# STEP092 Implementation Failure Log

```text
Runtime: STEP092_SESSION_CONTEXTUAL_FOLLOW_UP_AND_STABLE_ENTITY_FOCUS / 2.76.0
State: IMPLEMENTED_STATIC_VALIDATION_ONLY_TEST_EXECUTION_DEFERRED_BY_USER_MINIO_PENDING
```

## R1 — Focus state comparison was initially written with the wrong identity form

An early edit compared a focus state through an inappropriate string/enum identity expression. Source review caught it and the code now uses the typed `SessionContextFocusState` value consistently.

**Recurrence rule:** Session state is a typed enum; use value equality/enum membership, never Python object identity against string values.

## R2 — Stored focus decoding was initially too permissive

The first `from_mapping()` draft converted arbitrary values with `str(...)` and tolerated extra keys. That could turn corrupted, hash-recomputed metadata into superficially valid identifiers. It was tightened to exact-key and exact-type decoding; catalog revision also rejects booleans masquerading as integers.

**Recurrence rule:** integrity-protected Product metadata must use strict canonical decoding, not coercive parsing.

## R3 — GET result fence originally allowed zero returned records

The first result fence rejected wrong/multiple stable IDs but allowed zero records, intending to represent a deleted entity. With the current MCP result shape, zero records cannot prove which stable ID the model actually supplied as Tool arguments. Accepting zero could therefore hide a wrong argument. The contract was tightened to require exactly one returned stable entity matching the immutable type/ID hint.

**Recurrence rule:** when argument provenance is not independently observable, fail closed rather than treating absence as proof of correct targeting.

## R4 — Stable-ID wording initially overstated direct argument control

A routing reason said the stable ID was reused “only as read Tool input.” The SDK currently uses a named Tool choice while the model still constructs Tool arguments. The wording was corrected to “bound in immutable read routing hint,” and result evidence is independently fenced.

**Recurrence rule:** documentation/reasons must distinguish Tool selection, routing hints, model-produced arguments, and observed Tool output.

## R5 — Unbounded Session focus lifetime could reuse a stale entity

The first focus design preserved the most recent Organization entity across arbitrary later successful Turns. That could make a much later targetless expression such as `연락처는?` resolve to an entity that was no longer conversationally current. The stored focus now records `source_turn_count` and is usable only when it equals the Session's latest committed `turn_count`. Ambiguous route-only clarification does not advance the Turn and therefore keeps its candidate set; an unrelated successful Turn makes the old focus stale.

**Recurrence rule:** conversational references require an explicit recency/invalidation rule; durable storage alone must not imply indefinite referential authority.

## R6 — Validation remains pending

STEP092 regression, deterministic acceptance, partition and Windows launchers are prepared but not executed due the user-directed test hold. No acceptance count is claimed.

## R7 — Ambiguous display candidates initially exceeded persisted focus candidates

The inherited ambiguous normalizer could expose up to 30 stable-ID candidates, while the STEP092 Session focus contract persists at most 20. That could show a candidate to the user that could not exist in the next-turn bounded candidate set. The ambiguous public candidate list is now capped at the same 20-candidate bound as Session focus.

**Recurrence rule:** a user-visible disambiguation candidate set and the durable next-turn selection set must have the same bound and ordering.

## R8 — Admin/Service preflight originally evaluated routing twice

The existing preflight flow first called the public route method and then called the router again to build model input. With Session focus, a concurrent committed Turn could change the focus between those two reads, making the returned route and admitted immutable routing hint disagree. STEP092 now snapshots Session focus once and creates exactly one route decision per preflight in both Service and Admin paths. Admin model-request wrapping was also aligned with the Organization Context root/read Agent IDs.

**Recurrence rule:** one governed preflight must be based on one routing decision and one Session-context snapshot; never reroute the same request before admission.

