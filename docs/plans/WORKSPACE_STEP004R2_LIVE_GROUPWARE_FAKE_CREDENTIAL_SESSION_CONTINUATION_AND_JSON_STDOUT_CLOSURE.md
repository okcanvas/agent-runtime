# WORKSPACE_STEP004R2_LIVE_GROUPWARE_FAKE_CREDENTIAL_SESSION_CONTINUATION_AND_JSON_STDOUT_CLOSURE

Version: 0.4.2

## Parent evidence

- Official Windows deterministic baseline: STEP003R2 / 0.3.2, 27/27.
- STEP004R1 Windows deterministic readiness: 30/30 PASS.
- STEP004R1 Windows Live: 18/22 FAILED after actual `gpt-4.1` model calls and two successful Runtime runs.

## Scope

1. Use the Node Groupware API Fake's exact product token in the Live Connector configuration.
2. Route Session-referential restatements to the Root Session without re-invoking the child.
3. Keep explicit refresh/re-query, write, draft, and automation routing unchanged.
4. Validate real SDK Session continuity without assuming deterministic mock item counts.
5. Keep stdout as one JSON document; environment provenance diagnostics go to stderr.
6. Retain STEP004R1 process-shutdown-before-temp-cleanup and Workspace bytecode isolation.

## Acceptance split

- Deterministic readiness must pass before Live execution.
- Live must use `.env.local` or `.env.local.cmd`, actual OpenAI, actual Connector, and actual Node Example.
- Real enterprise Groupware remains outside this step.

## Local deterministic result

- Workspace readiness: 34/34 PASS
- Workspace unit tests: 51/51 PASS
- Runtime STEP087R2: 18/18 PASS
- Runtime focused: 107/107 PASS
- Deterministic E2E: 14/14 PASS
- Actual Windows Live: pending
