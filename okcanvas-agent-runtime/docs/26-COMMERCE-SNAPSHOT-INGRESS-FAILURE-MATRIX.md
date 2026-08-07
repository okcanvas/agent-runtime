# Commerce snapshot ingress failure matrix

## Purpose

STEP027 proves that the existing governed commerce ingress fails closed through the actual Control API and Product persistence boundary. It adds no adapter, authority, remote host, write operation, model call, Agent Tool, or successful business path.

## Matrix

| Case | HTTP | Safe code | Retryable |
|---|---:|---|---|
| authentication rejected | 502 | `COMMERCE_SNAPSHOT_SOURCE_AUTH_FAILED` | false |
| redirect | 502 | `COMMERCE_SNAPSHOT_RESPONSE_REJECTED` | false |
| wrong media type | 502 | `COMMERCE_SNAPSHOT_RESPONSE_REJECTED` | false |
| oversized response | 502 | `COMMERCE_SNAPSHOT_RESPONSE_TOO_LARGE` | false |
| malformed JSON | 502 | `COMMERCE_SNAPSHOT_INVALID` | false |
| invalid UTF-8 | 502 | `COMMERCE_SNAPSHOT_INVALID` | false |
| empty body | 502 | `COMMERCE_SNAPSHOT_INVALID` | false |
| item-count overflow | 502 | `COMMERCE_SNAPSHOT_INVALID` | false |
| upstream HTTP 503 | 502 | `COMMERCE_SNAPSHOT_RESPONSE_REJECTED` | false |
| transport unavailable | 503 | `COMMERCE_SNAPSHOT_SOURCE_UNAVAILABLE` | true |
| missing configuration | 503 | `COMMERCE_SNAPSHOT_SOURCE_NOT_CONFIGURED` | false |
| remote origin | 503 | `COMMERCE_SNAPSHOT_SOURCE_NOT_CONFIGURED` | false |
| invalid snapshot key | 422 | `COMMERCE_SNAPSHOT_REQUEST_INVALID` | false |
| unknown adapter | 502 | `COMMERCE_SNAPSHOT_DEFINITION_INVALID` | false |

The ingress still performs no automatic retry. `retryable=true` means an operator may submit a new explicit attempt after correcting a transient transport condition.

## Required fail-closed result

Every case must leave all of the following at zero:

- Submission;
- Task;
- Run;
- Event;
- Artifact;
- Evaluation;
- protected payload file;
- model gateway call.

The controlled source must receive no write method. A redirect must not be followed. Credentials and response-body sentinels must not appear in SQLite.


## Windows live acceptance

The Windows acceptance passed all 24 checks with the exact fourteen-case matrix, zero persistent Product state, zero source writes, zero model calls, and cleanup `COMPLETED`.
