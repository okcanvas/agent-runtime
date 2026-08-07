# Store replenishment multi-case product acceptance

## Purpose

STEP026 proves that the live-accepted governed commerce ingress and replenishment Agent are not accepted from one shortage fixture alone. It keeps the production boundary unchanged and exercises the same preflight, confirmation, Run, Artifact, Evaluation, retention, and cleanup flow over multiple business states.

## Valid cases

| Case | Expected status | Expected total | Main boundary |
|---|---:|---:|---|
| `case001-shortage` | `ACTION_REQUIRED` | 19 | existing 12/7/0 baseline |
| `case002-covered` | `READY` | 0 | all zero quantities and SKU ordering |
| `case003-tie-ordering` | `ACTION_REQUIRED` | 10 | equal quantity tie sorted by SKU |
| `case004-single-shortage` | `ACTION_REQUIRED` | 1 | one shortage and mixed zero quantities |

## Invalid case

`case005-invalid-duplicate-sku` returns a valid JSON document with a duplicated SKU. The source is read once, strict `StoreReplenishmentInput` validation rejects it, HTTP returns `COMMERCE_SNAPSHOT_INVALID`, and Product persistence counts remain unchanged.

## Unchanged safety boundary

- one allowlisted loopback `GET` adapter;
- zero source writes;
- no model call during acquisition;
- no Agent Tool or MCP;
- exact fingerprint confirmation;
- protected payload deletion after success;
- no raw source snapshot in SQLite or Events.


## Windows live acceptance

The user-reported Windows run passed all 22 checks with five reads, zero writes, four valid Runs/Artifacts/Evaluations, exact totals 19/0/10/1, duplicate-SKU rejection before persistence, successful payload deletion, and cleanup `COMPLETED`.
