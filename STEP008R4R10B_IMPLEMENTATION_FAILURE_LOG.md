# STEP008R4R10B Implementation Failure Log

## R10A post-CLI diagnostic blind spot

Observed on actual Windows: focused cross-domain Live FAILED 6/7 at `execute_establish-employee-focus`, while both diagnostic objects were null.

Root cause in acceptance harness: diagnostics were assigned only inside the non-zero CLI process branch. The Product CLI can catch a per-request error and exit process 0, after which the harness performed exact Run-cardinality assertions without first persisting the CLI output and Run snapshot.

Correction: latest redacted CLI summary and visible Runtime Run summary are now assigned unconditionally before request-completion and cardinality assertions. Process exit success and request completion are separate checks. No Product fallback was added.
