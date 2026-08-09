# WORKSPACE-ISSUE-052 — CLI process success did not prove Product request completion or Run cardinality

Status: FIX_IMPLEMENTED_RERUN_REQUIRED

## Evidence

The user's actual R10A focused cross-domain Live rerun reported:

- state `FAILED`, 6/7;
- `failure_stage=execute_establish-employee-focus`;
- `failure_diagnostics.cli=null`;
- `failure_diagnostics.runtime=null`;
- `safe_error.type=RuntimeError`.

In the R10A harness, the non-zero CLI branch assigns `failure_cli_diagnostic` before raising. Therefore the observed null diagnostic rules out that explicit branch. The same execution stage contains the post-CLI exact Run-count `RuntimeError`, and the Product CLI catches per-request errors internally and can exit process 0. R10A only retained CLI diagnostics on non-zero process exit and therefore still lost the evidence needed to distinguish a rendered request error, zero Runs, or another cardinality mismatch.

## Correction

Always retain the latest redacted CLI observation and visible Runtime Run cardinality before post-CLI assertions. Treat `one_request_completed` as a separate required fact from process exit code. Never compensate with aliases or fallback routing.
