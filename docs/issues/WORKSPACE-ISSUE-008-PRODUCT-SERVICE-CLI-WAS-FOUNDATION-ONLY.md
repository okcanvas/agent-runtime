# WORKSPACE-ISSUE-008 — Product Service CLI was foundation-only

## Failure

The independent `okcanvas-agent-cli` project declared the correct Service API boundary but did not provide
an executable client. Users could not authenticate with an external Bearer, keep a Runtime Assistant
Session across prompts, execute the automatic Assistant route, confirm a governed Run, consume persisted
SSE, or display the final Artifact.

## Correction

`WORKSPACE_STEP002_PRODUCT_SERVICE_CLI_INTERACTIVE_CONVERSATION_FLOW` promotes the CLI to
`CLI_STEP001_PRODUCT_SERVICE_INTERACTIVE_CONVERSATION_CLIENT` / `0.2.0` and retains Runtime, Connector,
and Example product bytes unchanged.

## Recurrence gates

- Product CLI acceptance must pass 10/10.
- Two consecutive scripted prompts must reuse one Runtime Assistant Session.
- All CLI requests must use `/v1/service/**` and External Bearer authority.
- Runtime/Connector source imports and administrator headers/routes remain forbidden.
