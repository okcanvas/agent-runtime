# STEP003B — Codex bytecode suppression fix

## Objective

Prevent Python commands launched by Codex from creating `__pycache__` inside disposable or read-only
workspaces, so Windows cleanup can complete after an otherwise successful STEP003 run.

## Confirmed code evidence

The independent pytest validator already exports `PYTHONDONTWRITEBYTECODE=1`. Both Codex gateway
implementations copied only a fixed host allowlist and omitted that variable. The second live run
reported direct Python execution and cleanup failure on `src/inventory/__pycache__`.

## Scope

- add `PYTHONDONTWRITEBYTECODE=1` to read-only and workspace-write Codex subprocess environments;
- assert the variable in both gateway contract tests;
- execute a child Python import and prove that no bytecode directory is created;
- preserve every existing STEP003 write, diff, budget, validation, and cleanup control;
- update baseline, HANDOFF, Evidence, package name, and validation record.

## Non-scope

- external project write;
- arbitrary shell access;
- MCP, API, SSE, UI, or STEP004 approval/resume;
- accepting cleanup warnings as full STEP003 completion.

## Acceptance

Static acceptance requires compileall, the complete test suite, fixture failure→repair validation,
reference integrity 4/4, and package re-extraction validation. Live completion still requires a
Windows rerun with `state=PASSED`, `core_acceptance_passed=true`, and `cleanup.state=COMPLETED`.
