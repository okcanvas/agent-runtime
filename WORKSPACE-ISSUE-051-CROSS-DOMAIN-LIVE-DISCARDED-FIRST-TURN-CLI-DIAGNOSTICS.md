# WORKSPACE-ISSUE-051 — Cross-domain Live discarded first-Turn CLI diagnostics

Current Workspace: WORKSPACE_STEP008R4R10A_CROSS_DOMAIN_LIVE_FAILURE_DIAGNOSTIC_CLOSURE
Workspace Version: 0.8.4-r10a
Current Runtime: STEP094_CROSS_DOMAIN_STABLE_FOCUS_AND_GROUPWARE_CONTEXT_FILTER
Runtime Version: 2.78.0

## Status

FIX_IMPLEMENTED_LIVE_RERUN_REQUIRED

## Observed Windows evidence

The actual focused STEP094 cross-domain Live gate returned:

```text
state=FAILED
passed_checks=6
total_checks=7
failure_stage=execute_establish-employee-focus
safe_error.category=LIVE_EXECUTION_FAILED
safe_error.type=RuntimeError
```

The first route had already completed, so the failure occurred while the Product CLI was executing the first Organization Context Turn (`김선임 연락처`). No calendar/notice cross-domain Turn was reached.

## Root diagnostic defect

`run_workspace_step008r4r10_cross_domain_live_acceptance.py` already captured the Product CLI return code, stdout, stderr and output encodings via the canonical `run_command()` helper. It appended a subset to `cli_summaries`, then raised `RuntimeError` when the CLI return code was non-zero. The exception payload discarded `cli_summaries`, so the persisted evidence retained only the generic `RuntimeError` category and failure stage.

The actual first-Turn failure cause therefore cannot be reconstructed from the R10 JSON alone.

## Correction

R10A does not change Product execution semantics. On a non-zero Product CLI exit it now persists, after the existing secret redaction:

- case ID;
- CLI return code;
- whether the CLI completed one request;
- exact redacted stdout/stderr;
- stdout/stderr encodings;
- redacted command;
- latest Runtime Run summary when retrievable;
- latest event types, Tool names, `run.failed` payloads and normalization payloads;
- diagnostic collection error type if Runtime evidence collection itself fails.

The gate remains FAILED. Diagnostic collection never converts failure to success.

## Recurrence prevention

- Never discard diagnostics already captured before raising a harness failure.
- Never add a helper alias, display-name fallback, Tool fallback or compatibility shim to make the first Turn pass.
- The next Windows run must identify the canonical owner failure from the persisted diagnostic evidence before Product code is modified.
