# Interactive Agent Runner Foundation

Open `http://127.0.0.1:<OKCANVAS_API_PORT>/runner` after starting the Control API.

The page is a local governed execution surface, not a replacement for the read-only Operations
Console.

## Required local environment

The Control API requires distinct values for:

```text
OKCANVAS_CONTROL_ADMIN_KEY
OKCANVAS_RUN_SUBMITTER_KEY
OKCANVAS_PROTECTED_PAYLOAD_KEY
OPENAI_API_KEY
OKCANVAS_AGENT_MODEL
```

Keys must have at least 16 characters. The admin and Run-submitter keys must differ.

## Normal flow

```text
select Agent
→ enter request
→ governed preflight
→ inspect fingerprint and Runtime binding
→ copy and type exact confirmation
→ existing Task/Run execution
→ persisted Event view
→ verified final-output Artifact
→ compatible recorded Evaluation
```

For `local-text-metrics-agent`, the Runner prepares the approval request and then stops at the
approval boundary. Use the dedicated Approval Operator for approve/reject.

## Security properties

- two separate authority headers;
- current-tab `sessionStorage` only;
- no raw request in Product SQLite or canonical Events;
- no direct `/v1/runs` mutation;
- no approval decision in the Runner;
- verified Artifact content only;
- no host Artifact path returned to the browser.

## Limits

This is the first walking-skeleton surface. It uses persisted canonical Event SSE, not native SDK
text/tool delta streaming. Handoff, nested Agents, Session, and Guardrails remain disabled.
