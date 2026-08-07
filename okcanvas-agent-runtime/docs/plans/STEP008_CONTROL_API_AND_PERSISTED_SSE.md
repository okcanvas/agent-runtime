# STEP008_CONTROL_API_AND_PERSISTED_SSE

## Status

`IMPLEMENTED_ASGI_ACCEPTED_NETWORK_LIVE_PENDING`

## Objective

Expose the STEP005 durable Task/Run/Event state and STEP007 generic execution through a small local-admin-only FastAPI boundary. SSE must replay only product-owned persisted canonical Events and must never expose OpenAI Agents SDK event classes directly.

## Scope

- create one generic Agent Run asynchronously;
- read Task and Run state;
- read persisted canonical Run Events;
- resume SSE with `Last-Event-ID` or cursor;
- emit heartbeat comments while a Run is non-terminal;
- stop SSE after a terminal product Event;
- cancel one active local-process Run and persist `run.cancelled`;
- use canonical HTTP error bodies and status codes;
- require one local administrator key for all control endpoints;
- enforce the constitution that `/reference` is consulted but never directly imported.

## Non-scope

- tenant or organization authorization;
- distributed worker lease;
- active Run recovery after process restart;
- SDK Session or RunState;
- MCP, Handoffs, multi-Agent execution;
- public CORS, OpenAPI UI, browser UI;
- raw SDK stream forwarding;
- direct import, execution, or path dependency from `reference/upstream`.

## Reference inspection and decisions

### ADAPT

- `reference/upstream/openai-agents-streaming-api/src/api/utils/agent_router.py`
  - Adopted the idea of a bounded per-capability HTTP adapter and SSE response.
  - Replaced direct `Runner.run_streamed()` forwarding with persisted product Event replay.
  - Rejected HTTP-200 error envelopes, raw exception text, permissive CORS, and raw request logging.

### REJECT as a public contract

- `reference/upstream/openai-agents-python-0.19.0/src/agents/stream_events.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/run_internal/streaming.py`
  - SDK streaming classes remain internal implementation details.
  - Public SSE is built only from `run_event` records and the stable `okcanvas-control-event-v1` schema.

### ADAPT

- `reference/upstream/openai-cs-agents-demo/python-backend/server.py`
  - Adopted a thin application boundary around an Agent service.
  - Rejected process-memory conversation state, unauthenticated mutation, and implicit ownership.

### DEFER

- SDK Session and RunState persistence;
- network-level live model acceptance;
- distributed worker leasing and restart recovery;
- external identity provider and tenant ownership.

## Architecture

```text
HTTP local-admin request
  -> Control API
  -> LocalExecutionCoordinator
  -> GenericAgentExecutionService
  -> official installed openai-agents package
  -> SQLite Task/Run/Event + Artifact

SSE client
  -> persisted run_event sequence
  -> cursor / Last-Event-ID replay
  -> heartbeat while non-terminal
  -> close after terminal Event
```

`/reference` is not part of the import graph. `scripts/verify_no_reference_imports.py` statically checks executable Python and project dependency declarations.

## Acceptance

- unauthenticated control access returns 401;
- create returns 202 and durable Task/Run IDs;
- Task and Run reach SUCCEEDED through a deterministic gateway;
- canonical Event sequences are monotonic;
- SSE resumes strictly after sequence 5;
- terminal SSE includes `run.completed` and closes;
- heartbeat is emitted for a non-terminal Run;
- cancel transitions Task and Run to CANCELLED and appends `run.cancelled`;
- malformed input returns canonical 422 error body;
- SDK event class names are absent from public payloads;
- raw request, API key, and local admin key are absent from SQLite;
- all four reference trees remain unchanged;
- direct `/reference` imports are absent.

## Retained limitation

The coordinator is intentionally single-process. Persisted completed Events survive restart and can be replayed, but an active in-memory model call is not resumed after process loss. That requires a later durable worker lease design.
