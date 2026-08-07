# Local Run Submission Boundary

## Authority

`LOCAL_OPERATIONS_READER` can inspect product state. It cannot submit a Run. The future submit surface must establish `LOCAL_RUN_SUBMITTER` authority independently of the read-only console session.

## Preflight fingerprint

The canonical fingerprint contains only:

- policy SHA-256;
- authority scope;
- Agent Definition ID, Version, and SHA-256;
- selected model identifier;
- normalized input SHA-256;
- derived execution mode.

The raw input and raw idempotency key are never stored in the preflight table.

## Confirmation

Read-only execution requires an exact deterministic challenge:

```text
RUN <agent-id>@<version> <fingerprint-prefix>
```

A generic `confirm=true` is not the future console contract.

## Execution mode

| Capability | Mode | STEP017 execution |
|---|---|---|
| No local Tool, read-only MCP only | `IMMEDIATE_AFTER_CONFIRMATION` | Designed, not scheduled by preflight |
| Local Tool | `APPROVAL_INTERRUPTED` | Requires persisted SDK RunState approval path |
| Write MCP | `PROPOSAL_ONLY` | Disabled |
| Handoff or Session orchestration | `PROPOSAL_ONLY` | Disabled |

## Idempotency

The raw `Idempotency-Key` is hashed before persistence. Reusing the same key for the same request fingerprint returns the same submission record. Reusing it for another fingerprint fails closed.

## Payload protection

STEP017 deliberately uses `NOT_PERSISTED_STEP017`. The preflight service proves that it can make and persist a policy decision without storing the raw request. A later execution step must add an explicit protected payload store rather than quietly placing raw input in SQLite, Events, URLs, logs, or approval metadata.

## Existing direct Run route

`POST /v1/runs` remains available only as a compatibility implementation and is disabled by default in `app_from_environment`. Controlled tests can enable it explicitly. The operations console does not call it.
