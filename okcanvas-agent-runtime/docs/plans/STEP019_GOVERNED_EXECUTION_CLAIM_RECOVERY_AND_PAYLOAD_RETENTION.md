# STEP019 — Governed Execution Claim Recovery and Payload Retention

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_PENDING`

## Goal

Recover stale governed read-only execution claims without creating another Product Task/Run, fence obsolete scheduled work, and define deterministic encrypted-payload retention and deletion.

## Reference inspection

- `reference/upstream/openai-agents-python-0.19.0/src/agents/run_state.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/result.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/sandbox/session/base_sandbox_session.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/sandbox/session/sandbox_client.py`

## Implemented

- immutable lifecycle policy and SHA;
- 30-second local claim lease;
- three-attempt bounded stale recovery;
- raw generation token kept in memory, SHA persisted;
- atomic generation-fenced start;
- `run.execution.recovered` canonical Event;
- immediate successful payload deletion;
- seven-day failed/cancelled retention;
- 24-hour unconfirmed payload expiry;
- explicit cleanup batch limited to 100;
- deletion-failure ledger state;
- authenticated recovery and cleanup APIs;
- terminal completion observer;
- deterministic tests and Windows launcher.

## Acceptance

`sh_run_step019_acceptance.cmd` validates 18 checks covering successful cleanup, failed retention/deadline/cleanup, stale recovery, attempt bounds, old-generation fencing, one new start, canonical recovery and retention Events, read-only console, and unchanged Reference trees.

## Explicit non-scope

- active `RUNNING` Run recovery or SDK resume;
- automatic startup recovery;
- distributed workers or leases;
- cross-process exactly-once claims;
- local Tool approval interruption;
- console mutation.
