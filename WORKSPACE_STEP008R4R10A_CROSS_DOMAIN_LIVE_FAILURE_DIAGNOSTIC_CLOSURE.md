# WORKSPACE STEP008R4R10A — Cross-domain Live failure diagnostic closure

Current Workspace: WORKSPACE_STEP008R4R10A_CROSS_DOMAIN_LIVE_FAILURE_DIAGNOSTIC_CLOSURE
Workspace Version: 0.8.4-r10a
Current Runtime: STEP094_CROSS_DOMAIN_STABLE_FOCUS_AND_GROUPWARE_CONTEXT_FILTER
Runtime Version: 2.78.0

## Purpose

Preserve sufficient, redacted evidence to diagnose the actual first-Turn STEP094 focused Windows Live execution failure without changing Product semantics.

## Actual failure

```text
state=FAILED
passed_checks=6/7
failure_stage=execute_establish-employee-focus
safe_error=LIVE_EXECUTION_FAILED / RuntimeError
```

This means preflight and cleanup succeeded but the Product CLI returned non-zero during the first `김선임 연락처` Turn. Cross-domain calendar/notice execution was not reached.

## Changes

Only Workspace acceptance diagnostics/governance are changed. The focused harness now includes `failure_diagnostics.cli` and `failure_diagnostics.runtime` in the FAILED evidence payload. Values originate from canonical `run_command()` redacted output and Service API Run/Event evidence. Failure remains failure even when diagnostics are successfully collected.

## Explicit non-goals

- no helper alias;
- no legacy/canonical field fallback;
- no display-label fallback for stable IDs;
- no Tool fallback;
- no retry with weakened arguments;
- no Runtime Product change;
- no claim that STEP094 is accepted.

## Next gate

Re-run `sh_run_workspace_step008r4r10_cross_domain_live_acceptance.cmd`, inspect persisted failure diagnostics, then correct only the canonical owner defect demonstrated by that evidence.
