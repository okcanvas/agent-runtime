# WORKSPACE STEP008R4R10B — Post-CLI Request Completion and Run Cardinality Diagnostic Closure

Current Workspace: WORKSPACE_STEP008R4R10B_POST_CLI_REQUEST_COMPLETION_AND_RUN_CARDINALITY_DIAGNOSTIC_CLOSURE
Workspace Version: 0.8.4-r10b
Current Runtime: STEP094_CROSS_DOMAIN_STABLE_FOCUS_AND_GROUPWARE_CONTEXT_FILTER
Runtime Version: 2.78.0

## Scope

Workspace acceptance diagnostics only. Runtime Product behavior is byte-preserved from R10/R10A.

The actual R10A Windows focused cross-domain Live rerun again failed at `execute_establish-employee-focus` with 6/7 checks, while both `failure_diagnostics.cli` and `failure_diagnostics.runtime` were null. Code inspection proves the non-zero CLI branch was not the observed branch because that branch assigns CLI diagnostics before raising. The remaining explicit `RuntimeError` path in the stage is post-CLI exact Run-cardinality enforcement. In addition, the Product CLI intentionally catches per-request errors and may exit process 0 after printing the error, so subprocess return code cannot stand in for request completion.

## Correction

The focused harness now, before any post-CLI assertion:

1. persists the latest already-redacted CLI stdout/stderr, return code, encodings, command, and `one_request_completed` observation;
2. collects and persists visible Runtime Run cardinality and bounded per-Run status/event/Tool/failure/normalization summaries;
3. fails if the process return code is non-zero;
4. fails if the Product request did not actually complete even when the process exit code is zero;
5. enforces the exact expected Run cardinality only after those diagnostics are durable in the evidence payload.

No alias, helper fallback, display-name fallback, Tool fallback, compatibility shim, retry broadening, or Runtime Product behavior change is permitted in this corrective wave.

## Promotion

NOT_READY. The same Windows focused cross-domain Live command must be rerun and its new diagnostics must identify the canonical owner defect before Product correction.
