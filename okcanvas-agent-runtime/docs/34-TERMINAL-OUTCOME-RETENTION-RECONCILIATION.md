# STEP035 — Terminal Outcome Retention Reconciliation

STEP035 strengthens the reusable Agent Runtime after STEP034 closed the earlier `RUNNING` process-loss state. It addresses a later process-loss window: the Product Task and Run may already be terminal while the governed submission and protected-payload retention observer has not completed.

## Confirmed defect

`GenericAgentExecutionService` persists the Product outcome first. `LocalExecutionCoordinator` invokes `GovernedExecutionLifecycleService.observe_run_completion()` afterward. Process loss between those operations can leave:

- Product Task/Run `SUCCEEDED`, `FAILED`, or `CANCELLED`;
- submission still `EXECUTION_STARTED`, or partially terminalized;
- previous claim metadata still present;
- success payload not deleted, or failure/cancel payload still carrying the old preflight TTL;
- no `payload.retention.applied` Event.

No model re-execution is required or permitted because the Product outcome is already durable.

## Explicit reconciliation boundary

Authenticated local operators use:

```http
POST /v1/run-submissions/reconcile-terminal-outcomes
```

with the exact phrase:

```text
RECONCILE_TERMINAL_RUN_OUTCOMES_AFTER_PROCESS_RESTART
```

Candidates require matching terminal Product Task and Run states. A still-`EXECUTION_STARTED` row must belong to a different previous process. Already-terminal partial rows with cleared ownership are also repairable.

## Outcome rules

- `SUCCEEDED`: submission becomes `EXECUTION_SUCCEEDED`; protected payload is deleted immediately; exactly one `payload.retention.applied` Event records `DELETED`.
- `FAILED`: submission becomes `EXECUTION_FAILED`; protected payload is retained for the configured investigation window; exactly one retention Event records `RETAINED`.
- `CANCELLED`: submission becomes `EXECUTION_CANCELLED`; the same failed/cancelled investigation retention applies.

The original Task, Run, terminal Event, and successful Artifact remain authoritative. No replacement Product state is created.

## Safety properties

- no scheduler, model, MCP, or Tool call;
- no Run re-execution;
- old claim owner/token cleared;
- previous generation inactive because the Product Run is already terminal;
- successful Artifact preserved;
- no new Evaluation created;
- repeated reconciliation is a no-op;
- normal completion observer is idempotent for retention Events.

## Reference decision

The retained Agents SDK `result.py`, `run.py`, and `run_state.py` describe Runner results and explicit interruption/resume state. They do not own OKCanvas Product Task/Run, governed submission, encrypted payload retention, or post-Product observer durability. STEP035 therefore keeps terminal outcome reconciliation product-owned and does not invoke SDK resume.

## Deferred

- automatic startup mutation;
- automatic model retry or arbitrary in-flight resume;
- distributed leases;
- cross-process exactly-once external execution;
- heterogeneous second-Agent proof, which remains the next Runtime-centered audit candidate after Windows closure.
