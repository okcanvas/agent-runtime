# STEP043 — SQLite Session Runtime code audit

## Audited Reference

Primary immutable upstream files:

- `reference/upstream/openai-agents-python-0.19.0/src/agents/memory/session.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/memory/sqlite_session.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/run_internal/session_persistence.py`
- `reference/upstream/openai-agents-python-0.19.0/examples/memory/sqlite_session_example.py`
- corresponding upstream Session and Runner tests under `reference/.../tests/`.

Executable Runtime imports only the installed `agents` package. `/reference` remains immutable and import-forbidden.

## Findings

### SDK Session contract

The public protocol is intentionally small: `session_id`, `get_items`, `add_items`, `pop_item`, and `clear_session`. It stores conversation items, not Product Task/Run state.

### SQLite implementation

`SQLiteSession` accepts a caller-supplied Session ID and SQLite path. It persists a session table and ordered message table, serializes items as JSON, supports latest-item limits, and owns process-local file locks and explicit `close()` cleanup.

### Runner integration

The Runner session persistence layer reads existing history, merges it with the current turn input, avoids accidentally re-persisting prior history, and saves only items belonging to the new turn. Therefore Product code should pass the SDK Session object rather than manually concatenating or copying conversation history.

### Official example

The upstream example reuses one Session identity over sequential Runner calls and demonstrates automatic conversational continuity. It does not address authorization, Runtime drift, concurrency, Product metadata, or retention.

## Product gaps before STEP043

Before STEP043 the Runtime accepted only `session_mode=disabled`. There was no:

- Product Session ID/catalog;
- Agent/Runtime binding at Session creation;
- governed Session API;
- preflight Session fingerprint binding;
- one-active-Turn lease;
- safe canonical Session Event pair;
- explicit clear state;
- Interactive Runner Session controls.

## Adopted versus adapted

Adopted directly from installed SDK:

- `SQLiteSession`;
- Runner `session=` argument;
- SDK history merge/persistence semantics;
- explicit Session clear and close.

Product-owned adaptation:

- Session policy and metadata catalog;
- Agent/Runtime binding validation;
- governed authority and exact confirmation;
- active-Turn exclusivity;
- canonical safe metadata Events;
- Product/Evaluation/history lifecycle separation;
- clear authorization and fail-closed cleared state.

Rejected for V1:

- manually copying history into Product Events;
- treating Session as long-term memory;
- enabling compaction or encryption without a separate design;
- mixing Session with child Agents or Tools;
- allowing caller/model-selected SQLite paths;
- implicit migration after Agent or Runtime drift.

## Code locations

- `src/okcanvas_agent_runtime/sessions/` — policy, model, errors, service.
- `specs/runtime/sqlite-session-policy.json` — exact V1 policy.
- `src/.../agent_definitions/catalog.py` — `sqlite-v1` contract.
- `src/.../execution/runtime_binding.py` — Session path and fingerprint.
- `src/.../run_submission/` — Session ID ledger/fingerprint/confirmation.
- `src/.../execution/service.py` — active-Turn lifecycle and Events.
- `src/.../execution/openai_gateway.py` — installed SDK Session injection/close.
- `src/.../control_api/` — create/list/get/clear and preflight API.
- `src/.../interactive_runner/assets/` — Session metadata controls.
- `tests/test_sqlite_session_runtime.py` — policy/store/lease/clear/drift tests.
- `scripts/run_step043_acceptance.py` — two-turn governed proof.

## Audit conclusion

The correct P0 design is not a generic memory platform. It is one local SDK SQLite history backend surrounded by product-owned immutable identity, exact confirmation, concurrency control, safe evidence and explicit clear. This closes the minimum Session skeleton needed before Guardrail and integrated STEP045 work.
