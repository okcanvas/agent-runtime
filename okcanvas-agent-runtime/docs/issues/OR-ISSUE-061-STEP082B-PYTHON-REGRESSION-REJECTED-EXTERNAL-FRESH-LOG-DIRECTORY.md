# OR-ISSUE-061 — STEP082B Python regression rejected an external Fresh log directory

## Symptom

A Fresh-ZIP regression invoked the supported `--log-dir /tmp/...` option. The first pytest chunk completed, but checkpoint serialization raised `ValueError` because the external log path was not under the extracted repository root.

## Code-confirmed root cause

`_run_chunk()` always used `log_path.relative_to(ROOT)`. The CLI accepted arbitrary output and log directories, but the evidence serializer only supported repository-contained paths.

## Impact

Fresh Python rerun evidence could not be checkpointed outside the extracted ZIP. This could encourage writing validation logs into the candidate tree and contaminating Product inventory.

## Correction

`_evidence_path()` emits a repository-relative path when the log is inside the project and a normalized absolute path when it is external. No file content or host workspace is persisted into Product artifacts.

## Recurrence gate

- `test_step082b_python_regression_supports_external_fresh_log_directory`;
- Fresh-ZIP Python regression with external output and log directories.
