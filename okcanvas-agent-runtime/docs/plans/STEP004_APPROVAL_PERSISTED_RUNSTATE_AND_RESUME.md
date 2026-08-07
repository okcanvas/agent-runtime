# STEP004 — Approval, persisted RunState, and resume

## Objective

Place one SDK-native whole-run approval interruption in front of the live-accepted STEP003 disposable Codex write flow.

## Implemented scope

1. A minimal approval Agent requests only `codex_workspace_write(execution_id)`.
2. `needs_approval=true` interrupts before Codex starts.
3. `RunState.to_json(strict_context=True)` is written atomically.
4. Approval metadata and the RunState SHA-256 are written atomically outside the workspace.
5. A later process loads `RunState.from_json`, approves or rejects, and resumes.
6. Approval claims execution with an exclusive lock and invokes the existing STEP003 service once.
7. Terminal approval records reject repeated resume attempts.
8. Rejection must leave execution count zero and the workspace unchanged.

## Non-scope

- external repositories;
- REST/SSE/UI;
- MCP or PlanVM;
- per-command Codex approval;
- automatic recovery after a process crash in `EXECUTING` state.

## Important limitation

The exactly-once claim is proven for the normal persisted-resume path and terminal replay attempts. If a process crashes after the execution lock is claimed, the record remains fail-closed for manual review; automatic exactly-once recovery is not claimed.

## Live acceptance

```bat
sh_setup.cmd
sh_doctor.cmd
sh_run_step004_live_acceptance.cmd
```

The harness uses separate processes for prepare and resume and validates both APPROVE and REJECT branches.
