# STEP094R2 — Cross-domain Run submission admission owner closure

Runtime version: `2.78.2`

## Problem proven on Windows

R10C failed before Run creation with:

```text
[RUN_SUBMISSION_INVALID] Root Agent must declare exactly the Groupware read Sub-agent
```

The message was emitted by the retained STEP087 `GroupwareSessionDelegationCatalog` inside
`RunSubmissionBoundaryService.preflight()`.

## Canonical implementation

The current cross-domain Session root is resolved once through `CrossDomainSessionDelegationCatalog`.
Submission admission consumes the same immutable Product routing context as the gateway:

```text
organization-assistant-session-agent
  -> immutable routing context
  -> target_for_request()
  -> ORGANIZATION_CONTEXT -> organization-context-read
     OR
     GROUPWARE            -> groupware-read
```

Only the selected target MCP is included in submission delegated-access validation. The Runtime binding still
contains both child/MCP owners, so Session binding SHA remains a stable property of the long-lived Session.

A Turn that requests both delegated read capabilities fails closed. A Turn with no delegated read capability
may select no child. The historical dedicated `organization-context-session-agent` path remains explicit and
unchanged.

## Non-goals

No compatibility alias, display-name fallback, Tool fallback, route fallback, Session switching or weakened
binding check is introduced.

## Validation state

Static/Fresh package validation only. Focused Windows cross-domain Live must be rerun against R10D before
promotion. Broad executable tests remain deferred under the current MinIO hold.
