# WORKSPACE_STEP004_WINDOWS_LIVE_OPENAI_MAIN_ASSISTANT_STATELESS_GROUPWARE_SUBAGENT_E2E_READINESS

Version `0.4.0`

## Goal

Prepare one explicit Windows command that uses the Runtime's existing local environment file to perform a real OpenAI model call through the complete Main Assistant Groupware flow, without weakening the deterministic 27/27 baseline or persisting secrets.

## Deterministic readiness gate

```cmd
sh_run_workspace_step004_acceptance.cmd > log.txt
```

This gate verifies the immutable Runtime STEP087R1 17/17 evidence against the Runtime parent byte manifest, retained Workspace STEP003R2 Windows evidence, Workspace unit 44/44, all subprojects, deterministic full E2E 14/14, environment provenance, TLS harness boundaries, secret exclusions, packaging identity and Live fail-closed behavior. It does not call OpenAI and does not recursively rerun the complete Runtime acceptance.

## Windows Live gate

```cmd
sh_run_workspace_step004_live_acceptance.cmd > workspace-step004-live.log
```

The Runtime local environment file must be exactly one of:

```text
okcanvas-agent-runtime/.env.local
okcanvas-agent-runtime/.env.local.cmd
```

It must load non-empty `OPENAI_API_KEY` and `OKCANVAS_AGENT_MODEL`. Values are never written to evidence.

## Live flow

```text
Product CLI
→ actual Runtime Service API / persisted SSE
→ actual OpenAI Root model
→ Root SQLite Session
→ stateless Groupware Agent-as-Tool
→ actual OpenAI child model
→ child-owned MCP over local TLS
→ actual Connector ASGI process
→ actual Node Groupware API Fake process
→ parent final structured output
→ same Root Session continuation
```

## Promotion rule

STEP004 may be promoted to Windows Live accepted only from the user's actual Windows payload reporting `PASSED`, all checks true, actual model called, and real enterprise provider false. Provider quota, authentication, network and model-output failures remain distinct evidence and do not invalidate the deterministic STEP003R2 baseline.

## Local completion

```text
Workspace STEP004 readiness  29/29 PASSED
Workspace unit tests         44/44 PASSED
Runtime STEP087R1            17/17 PASSED
Runtime focused tests       104/104 PASSED
Deterministic full E2E       14/14 PASSED
Live preflight               FAIL-CLOSED / NO NETWORK
```
