# WORKSPACE_STEP003_MAIN_ASSISTANT_SESSION_STATELESS_GROUPWARE_SUBAGENT_E2E

Version: `0.3.0`

## Goal

Close one complete Product path without merging project ownership:

```text
Product Service CLI
→ Runtime Service API / persisted SSE
→ Runtime-owned Main Assistant SQLite Session
→ one stateless `groupware-read-agent` Agent-as-Tool call
→ child-owned `groupware-read` MCP client
→ external Groupware Connector MCP HTTP
→ Groupware API Fake Example REST
→ grounded final Artifact
→ second prompt in the same root Session with zero child call
```

## Invariants

- Root Session belongs only to `organization-assistant-session-agent`.
- Child Session is `NONE`; a new stateless child is constructed per matching turn.
- Child owns the Groupware MCP binding; root owns no Groupware MCP binding.
- Maximum child calls per turn is one.
- Groupware write capability remains disabled.
- Delegated identity exists only for the matching Groupware turn.
- Product CLI uses only External Bearer and `/v1/service/**`.

## Validation

- Runtime STEP087 deterministic acceptance: 15/15.
- Workspace full process E2E: 14/14.
- Workspace integrated STEP003 acceptance: 22/22 PASSED.
- Workspace structure tests: 29/29 PASSED.
- Retained STEP002R1 real Windows acceptance: 19/19.

## Explicit limits

This STEP does not claim a live OpenAI/model call, a real enterprise Groupware tenant, or current STEP003 Windows acceptance. The actual Connector and Node Example processes are exercised; the OpenAI Agents boundary is deterministic.

## ZIP-retained evidence

The immutable package includes `WORKSPACE_STEP003_LOCAL_DETERMINISTIC_ACCEPTANCE_SUMMARY.json` and `WORKSPACE_STEP003_MAIN_ASSISTANT_GROUPWARE_E2E_SUMMARY.json`. Detailed process records remain local mutable evidence and are linked by SHA-256 from those summaries.
