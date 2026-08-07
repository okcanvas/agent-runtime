# STEP064 — Bounded Encrypted SQLite Session Compaction V1

## Baseline

- predecessor: `STEP063A_WINDOWS_SYMLINK_INTEGRITY_TEST_PORTABILITY_FIX` version `2.43.1`, Windows live accepted;
- current version: `2.44.0`;
- current STEP: `STEP064_BOUNDED_ENCRYPTED_SQLITE_SESSION_COMPACTION_V1`;
- implementation state: deterministic accepted, Windows rerun pending.

## Fresh audit result

The STEP061 examples matrix placed Session hardening ahead of external Session backends. STEP063 closed strict local history encryption. A fresh audit of the STEP063A package and the pinned `openai-agents-python-0.19.0` source found that compaction is the next smallest product-valued Session boundary.

The pinned SDK supplies `OpenAIResponsesCompactionSession` and `responses.compact`, but its automatic Runner integration cannot be adopted unchanged. The product already owns Turn leases, item-count rollback, Task/Run state and encrypted SQLite persistence. If history is compacted inside `Runner` before Product commit, a later Artifact or Product-state failure can make the existing rollback boundary invalid because the original item count no longer exists.

STEP064 therefore adapts the SDK compaction primitive into a Product-owned post-commit maintenance path.

## Immutable V1 contract

```text
backend                         installed SDK SQLiteSession
history at rest                 STEP063 strict AES-256-GCM envelopes
compaction provider             OpenAI
API                              responses.compact
model                            gpt-4.1
mode                             INPUT_ONLY
trigger candidates               10
maximum input items              256
provider store                   false
previous_response_id             forbidden
automatic                        yes, after committed Session Turn
Runner-integrated compaction     no
concurrent Turn during compact   forbidden by DB lease
failure replacement              exact previous history restored
Product events                   metadata only
provider request count           recorded as 1 when started
provider token usage             not reported by pinned compaction result
```

Candidate selection exactly follows the pinned SDK contract: user messages and existing `compaction` items do not count toward the trigger.

## Transaction boundary

1. The normal SDK Runner receives only the strict encrypted Session wrapper.
2. The completed Agent Turn is counted and released through the existing Product Session transaction.
3. While the Product Run is still terminal-pending, STEP064 acquires a database-backed compaction lease using that same Run ID.
4. The encrypted history is decrypted locally and passed to `responses.compact` in input mode with `store=false`.
5. A non-empty strict reduction is required.
6. The encrypted replacement is verified, Product `item_count` is updated, and the lease is released.
7. The Product Run then reaches its existing terminal state.

A new Turn and Session clear are blocked while the compaction lease is held. Routine compaction failure releases the lease, retains the already committed Turn and exact previous history, and does not change the Product Run outcome.

## Provider and privacy boundary

- no `previous_response_id` is accepted or persisted;
- no provider response storage is enabled;
- no decrypted Session item is copied to Product Events, Artifact metadata or Product Session catalog;
- only lifecycle metadata, input/candidate/output item counts, policy identity, one provider request count and the fact that token usage is unavailable are exposed;
- the OpenAI client is created lazily only when the threshold is reached;
- official base URL and zero provider retries remain enforced;
- missing `OPENAI_API_KEY` below the trigger does not affect the Turn; at or above the trigger the maintenance attempt fails closed and leaves history unchanged.

## Failure contract

The wrapper snapshots the exact decrypted history before the provider call. SDK replacement errors and product validation errors must leave the exact previous history. Empty or non-reducing output is rejected. Input exceeding 256 items is not sent to the provider; the Session must be explicitly cleared before another Turn if the catalog count is already beyond this recovery ceiling.

## Composition coverage

The post-commit path is connected to:

- normal SQLite Session execution;
- Session + approval, both approved and rejected committed outcomes;
- Session + Handoff;
- Session + Guardrail;
- Session + Agent-as-Tool;
- Session + MCP.

Failed or rolled-back Turns do not invoke compaction.

## Non-goals

STEP064 does not add:

- manual compaction API or UI;
- TTL or silent expiration;
- key rotation or online re-encryption;
- automatic migration from plaintext;
- Redis, MongoDB, SQLAlchemy, Dapr or hosted Session backends;
- history export;
- `previous_response_id` continuity;
- compaction token accounting not exposed by the pinned API path;
- retry or fallback model selection.

## Validation

Deterministic acceptance must require:

- exact policy and SHA-256;
- STEP063 encryption source unchanged;
- exact SDK candidate semantics;
- no compaction wrapper passed to Runner;
- post-commit ordering and database lease;
- strict reduction and exact restore tests;
- historical Session composition regressions;
- Python compile, committed Node release, Node tests and Reference integrity.

No real OpenAI call is required for deterministic acceptance.

## Windows closure

```cmd
sh_run_step064_acceptance.cmd
```

STEP065 remains unselected until this command passes on Windows and the packaged ZIP receives a fresh audit.
