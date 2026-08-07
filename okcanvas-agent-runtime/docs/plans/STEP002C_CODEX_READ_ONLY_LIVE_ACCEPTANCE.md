# STEP002C_CODEX_READ_ONLY_LIVE_ACCEPTANCE

## Objective

Promote the implemented STEP002 Codex read-only vertical slice to a live-accepted baseline using retained Windows execution evidence.

## Current code evidence

STEP002B provided a fail-closed Windows environment loader, SDK/Codex readiness checks, a controlled Git fixture, read-only Codex integration, source-tree hashing, event journals, and thread persistence.

## In scope

- verify and retain the user-executed Doctor and two-run live acceptance output;
- require both runs to succeed;
- require the second run to resume the first Codex thread;
- require unchanged source-tree hashes;
- require known relevant files to be independently verified;
- record SDK, Codex CLI, model, usage, event, and artifact facts;
- update the runtime baseline to live accepted.

## Explicit non-scope

- workspace write;
- automatic fixes;
- MCP;
- arbitrary repositories;
- authoritative build/test execution by Codex;
- API/SSE/UI;
- production use.

## Acceptance criteria

- Doctor reports ready with no issues.
- First and second runs report SUCCEEDED.
- Source tree hashes remain identical before and after both runs.
- Same non-empty thread ID is retained and the second run reports resumed_thread=true.
- Acceptance summary reports PASSED with all checks true.
- Required fixture files are among independently verified inspected files.
- Raw evidence and canonical summary are packaged without secrets.

## Result

Accepted. The retained evidence records OpenAI Agents SDK 0.19.0, Codex CLI 0.145.0, two successful runs, thread resume, no mutation, and all acceptance checks passing.

## Known limitations

- pytest was unavailable in the Codex subprocess environment. The defect was reproduced directly and the test function was invoked directly on the second run.
- The acceptance consumed 168,949 total Agent tokens.
- Safety is established only for the controlled disposable fixture.
- The Codex Tool integration is upstream experimental.

## Next boundary

STEP003 may introduce write access only inside a disposable copy. Independent validation must execute outside Codex and remains the authority for build/test success.
