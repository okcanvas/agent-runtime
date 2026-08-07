# STEP016 — Operations Console Persisted Live View

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_PENDING`

## Goal

Update the selected Run timeline and status in the read-only local operations console from the existing persisted canonical Event SSE contract. Browser disconnects must resume from the last sequence without exposing SDK stream classes or introducing product mutations.

## Reference inspection

Inspected before implementation:

- `reference/upstream/openai-agents-streaming-api/src/api/utils/agent_router.py`
- `reference/upstream/openai-cs-agents-demo/python-backend/main.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/stream_events.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/run_internal/streaming.py`

## Decisions

### ADAPT

- authenticated same-origin SSE transport;
- a small product-owned browser stream adapter;
- explicit connection lifecycle and cleanup;
- live status separated from the persisted Event timeline.

### REJECT

- raw SDK stream objects as the browser contract;
- ephemeral in-memory queues as the replay source;
- wildcard CORS;
- native `EventSource`, because it cannot attach the required local-admin Header;
- prompt, instruction, model-output body, Tool argument, or Tool result disclosure;
- `/reference` import or execution.

## Product contract

- authoritative source: SQLite `run_event` rows;
- browser transport: authenticated GET `fetch()` with streamed SSE parsing;
- resume: both `cursor` query and `Last-Event-ID` Header;
- duplicate sequence suppression in the browser;
- prior selected Run stream aborted before another is opened;
- bounded reconnect delay, maximum five seconds;
- terminal Runs do not reconnect;
- at most the newest 500 Event rows remain rendered in the DOM;
- all console Product API methods remain GET-only.

## UI

The selected Run panel shows:

- Product Run status;
- live connection state;
- current persisted sequence cursor;
- optional auto-follow;
- local reconnect and stop controls;
- canonical Event sequence, type, source, and redacted payload.

Reconnect and stop affect only the browser connection. They do not mutate Task, Run, Agent, Evaluation, MCP, Approval, or deployment state.

## Non-scope

- Run creation or cancellation;
- live raw model token streaming;
- active Run process recovery after server restart;
- multi-worker fan-out;
- WebSocket transport;
- remote console deployment;
- compiled frontend framework.

## Acceptance

`sh_run_step016_acceptance.cmd` validates authenticated stream access, effective cursor replay, terminal completion, no-buffering Headers, browser duplicate suppression and abort behavior, bounded reconnect, GET-only operation, secret non-disclosure, unchanged Product/Evaluation databases, and immutable Reference trees.
