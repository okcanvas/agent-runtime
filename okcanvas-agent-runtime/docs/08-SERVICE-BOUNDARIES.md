# Service Boundaries

These are internal application services first, not network microservices.

## 1. Definition Catalog

Owns immutable references to Agent, Tool, MCP, validator, and policy specifications under `specs/`.

Responsibilities:

- load and validate definition IDs and versions;
- calculate definition fingerprints;
- resolve allowed Tools for an Agent;
- reject missing or conflicting contracts.

It does not execute Agents or Tools.

## 2. Task Service

Owns the durable user-level work request.

Minimum fields:

- `task_id`, type, status;
- input hash and optional protected payload reference;
- requested Agent definition ID/version;
- creation and terminal timestamps.

It does not store raw model traces as Task state.

## 3. Run Service

Owns an execution attempt.

Responsibilities:

- create attempts;
- enforce legal state transitions;
- assign execution leases;
- record usage totals and terminal outcome;
- link Session, RunState, Codex Thread, approvals, artifacts, and validations by reference.

## 4. Event Journal

Owns ordered canonical events per Run.

Each event has:

- `run_id` and monotonic sequence;
- canonical event type;
- source (`runtime`, `agent-sdk`, `codex`, `validator`, `operator`, `reference`);
- timestamp;
- payload schema version and payload hash;
- optional Tool call, Approval, Artifact, or Validation reference.

SDK stream events are normalized here rather than exposed directly.

## 5. Approval Service

Owns durable decisions and execution claims.

Responsibilities:

- pending decision record;
- immutable approve/reject decision;
- execution claim and replay protection;
- RunState artifact integrity verification;
- fail-closed recovery state.

STEP004 remains a controlled fixture implementation of this boundary. Its live acceptance is useful but no longer blocks core store work.

## 6. Artifact Service

Owns metadata and integrity for files produced or consumed by a Run.

Examples:

- Agent structured output;
- RunState JSON;
- Codex event JSONL and patch;
- validator stdout/stderr summaries;
- generated reports.

The database stores metadata and SHA-256. Large bytes live in an artifact storage adapter.

## 7. Validation Service

Runs deterministic validators outside the model and Tool process.

Responsibilities:

- named validator presets;
- fixed argument contracts rather than arbitrary shell strings;
- timeout, exit code, counts, and output hashes;
- authoritative pass/fail state.

## 8. Reference Catalog Service

Provides bounded read-only access to `reference/`.

Responsibilities:

- use `reference/CODE_MAP.md` and `MANIFEST` before broad search;
- resolve reference ID, version and immutable tree hash;
- search only inside approved reference roots;
- return path, line range, source classification and hash;
- never import or mutate upstream code.

Implemented in STEP006 with manifest/tree integrity verification, code-map-first search, bounded exact line reads, and optional canonical Run-event recording. It remains an internal application service, not an HTTP or MCP surface.

## 9. Execution Coordinator

Wraps the Agents SDK Runner.

Responsibilities:

- resolve one immutable Agent definition;
- attach only policy-approved Tools;
- start/resume a Run;
- normalize stream events;
- capture usage, trace IDs and response IDs;
- persist final structured output and errors.

It does not own product state transitions directly; it calls the Run and Event services.

## 10. Integration adapters

### Codex

Optional specialized coding Tool. It remains experimental-upstream, feature-gated, and replaceable.

### MCP

Introduced read-only after Tool policy and canonical state are available. The SDK's MCP manager and transports are reused.

### PlanVM

Receives an already-built executable plan. It is not Agent planning, memory, catalog, or orchestration infrastructure.

## 11. Recorded Run Evaluation Application Service

Connects durable execution evidence to deterministic Evaluation.

Responsibilities:

- require successful Product Task and Run state;
- load canonical Run Events;
- verify exactly one final-output Artifact and its storage boundary;
- validate the Artifact against the recorded immutable Agent definition;
- reconstruct model, Usage, Tool-call, and duration metrics;
- apply a selected Evaluation Case and persist only safe result metadata.

It never invokes the SDK Runner, a model, MCP, Codex, or `/reference` code.

## STEP018 protected payload and governed submission services

- `protected_payload`: owns AES-256-GCM encrypted request files, atomic write, path containment, file hash/length verification, key fingerprint, and authenticated decryption.
- `run_submission`: owns authority-independent policy classification, fingerprint/idempotency ledger, confirmation, atomic Product Task/Run binding, and execution claim state.
- `control_api`: authenticates local-admin and distinct Run-submitter credentials and exposes preflight/detail/confirm contracts.
- `execution`: remains the installed-SDK-facing generic Agent service; it receives plaintext only in memory after protected payload validation.

The protected payload service does not own Product Task/Run state. The submission service does not implement the SDK Runner. The execution service does not bypass submission policy or persist the raw request in Product Events.

## STEP019 governed recovery and retention services

- `run_submission.store`: owns claim generation, lease timestamps, recovery attempt counters, compare-and-set fencing, terminal submission state, and retention ledger metadata.
- `run_submission.execution`: owns initial and recovered scheduling preparation, but may start execution only through the active generation token.
- `run_submission.lifecycle`: owns terminal Run synchronization and protected-payload retention/deletion policy.
- `control_api.coordinator`: owns in-process task scheduling and reports terminal completion to the lifecycle observer; it does not decide retention policy.
- `protected_payload`: owns encrypted file deletion, but does not decide when a payload is eligible for deletion.

Recovery is intentionally narrow. Only a stale claim whose Product Task is `READY` and Product Run is `CREATED` may receive a new generation. `RUNNING` recovery, SDK-state resume, startup scanning, and distributed worker ownership are outside STEP019.

Payload lifecycle is policy-driven: successful terminal execution deletes immediately; failed/cancelled execution retains for the investigation window; unconfirmed payloads expire independently; cleanup is explicit and bounded. A deletion failure remains visible in the submission retention ledger.

## STEP020 governed local Tool approval services

- `tool_approval.gateway`: owns installed-SDK Function Tool construction, interruption, RunState serialization/restoration, and approve/reject calls.
- `tool_approval.state_store`: owns AES-256-GCM encrypted RunState files and integrity verification.
- `tool_approval.store`: owns approval metadata, decision CAS, resume generation fencing, and persisted Tool execution count.
- `tool_approval.service`: coordinates Product Task/Run transitions, protected payload access, SDK resume, Artifact creation, and terminal retention.

The approval store does not own Product request content. Product Events do not own or reconstruct SDK RunState.
