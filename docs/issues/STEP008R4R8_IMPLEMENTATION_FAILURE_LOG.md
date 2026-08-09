# STEP008R4R8 Implementation Failure Log

```text
Workspace: WORKSPACE_STEP008R4R8_RUNTIME_STEP092_SESSION_CONTEXTUAL_FOLLOW_UP_AND_STABLE_ENTITY_FOCUS
Runtime: STEP092_SESSION_CONTEXTUAL_FOLLOW_UP_AND_STABLE_ENTITY_FOCUS / 2.76.0
Test execution: DEFERRED_BY_USER_UNTIL_MINIO_READY
```

## W1 — Non-structural call-site patch inserted Session focus in the wrong constructor

During implementation, a broad text replacement inserted `session_context_focus=self._assistant_session_focus(request.session_id)` into a `DelegatedMCPIdentity.create()` call in Service capability reporting. That scope had no `request` variable and the constructor does not own Session routing context. Source-wide call-site inspection found the invalid insertion before packaging and it was removed.

**Recurrence rule:** after changing a repeated call signature, enumerate every new argument occurrence and inspect each call site semantically; do not trust text replacement.

## W2 — One Assistant preflight call site initially missed the Session focus argument

The first replacement updated the primary Assistant route but did not update every route/preflight invocation. Grep over all `session_context_focus` and router call sites found and corrected the missing preflight path.

**Recurrence rule:** route and preflight are paired Product surfaces; any new routing input must be traced through both Admin and Service paths.

## W3 — Product source changed PostgreSQL current table inventory without changing historical evidence

Adding `product_session_context_focus` changes the current PostgreSQL topology from the historical 15-table STEP091B3R1 live package to 16 tables. Rewriting historical 15/15 evidence would be false. The current contract records 16 as test-pending and preserves STEP091B3R1 evidence unchanged.

**Recurrence rule:** distinguish immutable historical live evidence from current expected topology whenever schema source changes.

## W4 — Tests intentionally not run

No unit, deterministic, Windows, Live OpenAI, PostgreSQL-live, or Object-Storage-live suite was run. This is not a hidden failure: it follows the user's explicit test hold until MinIO is prepared. Static checks must never be described as acceptance.

## W5 — Session-aware preflight exposed a pre-existing double-routing race

Service/Admin Assistant preflight previously produced a public route and then independently reran routing before submission. STEP092 made this unsafe because stable Session focus can change after another committed Turn. The current implementation derives route response and model request from one decision/focus snapshot.

**Recurrence rule:** route decisions carrying stable references are admission inputs; do not recompute them inside the same preflight.

## W6 — Admin model-request wrapping omitted Organization Context Agent IDs

Service preflight already wrapped Organization Context root/read Agent requests with the immutable Product routing context, while Admin preflight only wrapped default/session Agents. STEP092's GET evidence fence depends on that immutable hint. The Admin allowlist is now aligned with Service for Groupware/Organization Context Agent IDs.

**Recurrence rule:** Admin and Service preflight surfaces must preserve the same immutable routing context for the same selected Agent family.

