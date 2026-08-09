# STEP092 Session Contextual Follow-up and Stable Entity Focus

Current Runtime: STEP092_SESSION_CONTEXTUAL_FOLLOW_UP_AND_STABLE_ENTITY_FOCUS
Runtime Version: 2.76.0

## Problem confirmed in source

`OrganizationAssistantRoutingService.route()` previously received a `session_id` but no stable entity/candidate state from the preceding Organization Context Tool execution. The only session-aware routing branch handled explicit answer restatement. Natural follow-up therefore depended on model context rather than a deterministic Product-owned stable identity boundary.

## Runtime design

- `SessionContextFocusObservation` is canonical JSON with SHA-256 integrity.
- Focus candidates contain only bounded entity type, stable ID, display label and selected evidence qualifiers.
- `product_session_context_focus` is separate metadata with source Run, source committed-Turn count, and update timestamp.
- focus loading verifies active Session, encrypted-history key binding, and last-committed-Turn recency.
- execution captures focus from normalized MCP Tool metadata and commits it with successful `release_turn`.
- contextual routing is policy-bounded and happens before ordinary session restatement routing.
- resolved focus forces a named GET Tool choice; ambiguous focus blocks model guessing.
- normalized GET evidence must return exactly one entity matching the immutable type/ID hint.
- the user-visible ambiguous candidate set and persisted next-Turn candidate set share the same 20-entry bound and order.
- Service/Admin preflight derive the response and model request from one routing decision/focus snapshot.

## Failure semantics

Malformed/tampered focus, key mismatch, conflicting focus observations, wrong Tool operation, wrong stable ID/type and zero/multiple GET results fail closed. A failed Turn does not replace the prior valid focus.

## Validation status

Deterministic/unit regression sources are prepared but not run. The retained Workspace Live runner covers the parent short-expression E2E only; a STEP092 contextual multi-turn Live scenario must be added/executed before `...windows_live_accepted` can become true. Both acceptance flags remain false.
