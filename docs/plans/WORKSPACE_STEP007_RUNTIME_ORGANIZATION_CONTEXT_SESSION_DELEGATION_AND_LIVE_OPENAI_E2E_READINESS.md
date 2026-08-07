# WORKSPACE STEP007 — Runtime Organization Context Session Delegation and Live OpenAI E2E Readiness

## Parent

- Windows deterministic: `WORKSPACE_STEP006` / `0.6.0` / 27/27.
- Windows Live OpenAI: `WORKSPACE_STEP004R2` / `0.4.2` / 22/22.

## Goal

Wire the production Organization Context Connector into Runtime without replacing the retained STEP084 local catalog, and provide an explicit Windows-only OpenAI Live E2E harness.

## Product boundary

`organization-context-session-agent` owns SQLite Session state and may invoke exactly one stateless `organization-context-read-agent`. The child alone owns the `organization-context-read` MCP server and its three unified read-only Tools. Production Organization Context remains database-SOT behind the Connector.

## Live path

Product CLI → Runtime Service API/SSE → actual OpenAI model → session root → stateless child → actual Organization Context MCP Connector → actual Node Organization Context API Example.

## Acceptance boundary

Local deterministic acceptance proves the Runtime wiring, retained parent evidence, actual Connector→Example HTTP integration, and a fail-closed Live preflight when `.env.local` is unavailable. Windows Live acceptance remains pending until the user executes the dedicated launcher.
