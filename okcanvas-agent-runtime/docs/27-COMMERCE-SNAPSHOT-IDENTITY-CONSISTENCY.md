# Commerce snapshot identity consistency

## Purpose

STEP028 closes an integrity gap in the existing governed read-only commerce ingress. Before this step,
the adapter validated the response structure and bound both the requested key hash and returned
snapshot hash, but it did not require the returned `snapshot_id` to equal the requested
`snapshot_key`.

A source could therefore answer:

```text
GET /v1/inventory-snapshots/requested-a
```

with a structurally valid snapshot whose body identified itself as `different-b`. That response was
cryptographically bound, but it represented a different business snapshot than the caller requested.

## Rule

After strict `StoreReplenishmentInput` validation and before canonicalization or governed preflight:

```text
returned snapshot_id == normalized requested snapshot_key
```

is required exactly.

Mismatch returns:

```text
HTTP 502
code=COMMERCE_SNAPSHOT_IDENTITY_MISMATCH
retryable=false
```

The safe error message does not echo the returned source identity.

## Fail-closed position

An identity mismatch must leave all of the following at zero:

- Submission;
- Task;
- Run;
- Event;
- Artifact;
- Evaluation;
- protected payload file;
- model gateway call.

The source is read once, no write method is sent, and neither the source credential nor the mismatched
response identity is persisted in SQLite.

## Non-scope

STEP028 adds no remote source, write authority, purchase-order creation, Agent, Tool, MCP, browser
mutation, tenant authorization, automatic retry, or distributed worker.
