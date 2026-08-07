# STEP017 — Local Run Submission and Approval Boundary Design

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_PENDING`

## Goal

Define and enforce the authority, confirmation, idempotency, payload-protection, approval, and failure-evidence boundary before exposing the first operations-console mutation.

## Reference inspection

Inspected before implementation:

- `reference/upstream/openai-agents-python-0.19.0/.agents/references/runstate-schema.md`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/run_state.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/result.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/tool.py`
- the existing project-owned STEP004 persisted approval implementation

## Reference decisions

### ADOPT

- `RunState.to_json()` and `RunState.from_json()` as the SDK pause/resume boundary;
- `RunState.approve()` and `RunState.reject()` for Tool-call decisions;
- approval identity bound to the exact Tool and provider call ID;
- conservative context serialization with no secrets.

### ADAPT

- separate Product submission preflight and SDK approval state;
- immutable Agent/MCP definitions as capability classification evidence;
- idempotency bound to a canonical request fingerprint;
- exact fingerprint confirmation rather than a boolean checkbox.

### REJECT

- authentication implying execution authority;
- generic confirmation booleans as the final submission contract;
- raw prompt, idempotency key, Tool arguments, or secrets in the submission ledger;
- direct `/reference` imports;
- console write controls in STEP017.

## Implemented

- immutable policy at `specs/submissions/local-run-submission-policy.json`;
- policy catalog and SHA verification;
- preflight capability classification;
- SQLite idempotency ledger with no raw input;
- same-key replay and different-fingerprint conflict;
- read authority rejection;
- authenticated read-only policy API;
- direct Run API disabled by default;
- console policy visibility while remaining GET-only;
- deterministic acceptance and Windows launcher.

## Non-scope

- protected payload encryption or vault;
- actual governed submission endpoint;
- approval decision API;
- Run scheduling from a preflight record;
- console submit button;
- write MCP, Codex write, deployment, or Handoff execution.

## Acceptance

`sh_run_step017_acceptance.cmd` validates sixteen checks covering authority separation, exact confirmation, idempotency replay/conflict, local Tool approval classification, raw payload/key non-persistence, zero Task/Run creation, direct API default denial, read-only console, and unchanged Reference trees.
