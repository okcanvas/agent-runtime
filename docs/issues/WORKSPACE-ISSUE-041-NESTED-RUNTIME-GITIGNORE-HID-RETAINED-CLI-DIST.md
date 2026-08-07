# WORKSPACE-ISSUE-041 — Nested Runtime .gitignore hid retained CLI dist

```text
Discovered in: WORKSPACE_STEP008R4R7A1_GIT_REPOSITORY_HYGIENE_AND_RETAINED_RUNTIME_DIST_TRACKING
Status: FIX_IMPLEMENTED_STATIC_VALIDATED_TEST_EXECUTION_DEFERRED_BY_USER
Product source impact: NONE
```

## Failure

The root Workspace `.gitignore` stated that `okcanvas-agent-runtime/clients/cli/dist/` is an accepted committed source artifact and intentionally avoided a global `**/dist/` rule. However, `okcanvas-agent-runtime/.gitignore` contained the unanchored `dist/` pattern.

Git applies the lower-level `.gitignore` to paths below that directory, so a fresh repository initialized from the accepted ZIP classified `okcanvas-agent-runtime/clients/cli/dist/*` as ignored. Already-tracked repositories could hide the defect because tracked files stay tracked.

## Reproduction

```text
git init
git check-ignore --no-index okcanvas-agent-runtime/clients/cli/dist/api-client.js
```

Before the correction, the path is ignored by the nested Runtime `dist/` rule.

## Correction

The Runtime `.gitignore` retains its normal `dist/` exclusion but adds explicit exceptions after it:

```gitignore
!clients/cli/dist/
!clients/cli/dist/**
```

The root `.gitignore` continues to ignore generated CLI/Connector/Example output without introducing a global `**/dist/` rule.

## Recurrence prevention

Git repository metadata must be validated from a **fresh untracked repository state**, not only from an already-tracked working tree. Required accepted generated source artifacts must have explicit `git check-ignore --no-index` sentinel coverage.

## Test status

Static Git-policy validation is allowed and has been performed. Product/unit/deterministic/live test execution remains deferred by user direction until MinIO is prepared; therefore this issue is not marked fully CLOSED by test evidence.
