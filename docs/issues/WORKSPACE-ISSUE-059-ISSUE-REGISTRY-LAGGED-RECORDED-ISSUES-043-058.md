# WORKSPACE-ISSUE-059 — Issue registry lagged recorded issues 043–058

## Status

FIXED_IN_R10ER1

## Observation

`docs/issues/ISSUE_REGISTRY.md` stopped at WORKSPACE-ISSUE-042 even though later issue documents 043–047 and 053–057 existed under `docs/issues/`, while 048–052 were retained at the Workspace root. A ZIP-only handoff therefore required filename discovery instead of one canonical issue index.

## Correction

R10ER1 appends issues 043–059 to the registry without rewriting the underlying historical issue documents. Current closure status is recorded in the registry where later accepted evidence supersedes the earlier `RERUN_REQUIRED` wording of historical issue files.

## Recurrence gate

Every newly created `WORKSPACE-ISSUE-NNN` document must receive one registry row in the same packaging wave. A future static gate should compare discovered issue IDs with registry IDs.
