# Control API and Persisted SSE

STEP008 exposes product state, not SDK internals.

## Endpoints

```text
GET  /healthz
POST /v1/runs
GET  /v1/tasks/{task_id}
GET  /v1/runs/{run_id}
GET  /v1/runs/{run_id}/outcome
GET  /v1/runs/{run_id}/events?after=N
GET  /v1/runs/{run_id}/events/stream?cursor=N
POST /v1/runs/{run_id}/cancel
```

All `/v1/**` endpoints require `X-OKCanvas-Admin-Key`. The initial product mode is explicitly `local-admin-only`; this is not a tenant authorization implementation.

## Public Event contract

SSE frames contain:

```text
id: <canonical run_event.sequence>
event: <canonical event_type>
data: <okcanvas-control-event-v1 JSON>
```

`Last-Event-ID` and `cursor` are merged by taking the greater value. Heartbeats are SSE comments and do not consume Event sequence values.

## Failure semantics

- invalid request: 422;
- missing live opt-in: 409;
- missing SDK/model/key or denied definition: 503;
- missing Task/Run: 404;
- non-terminal outcome: 409;
- cancelled outcome: 409;
- SDK execution failure outcome: 502;
- product state/internal failure: 500.

The API does not return raw exception messages or model request content.

## Restart boundary

The SQLite Event journal is durable. Reconnecting clients can replay completed persisted Events after a process restart. Active in-memory execution recovery is not implemented in STEP008.

## STEP017 direct submission restriction

`GET /v1/run-submission-policy` exposes the safe, read-only boundary metadata. `POST /v1/runs` is now disabled by default in environment-started servers and returns `403 DIRECT_RUN_SUBMISSION_DISABLED`. Controlled compatibility tests must opt in explicitly. The future governed submission API will use separate submit authority, mandatory idempotency, exact fingerprint confirmation, and protected payload storage.
