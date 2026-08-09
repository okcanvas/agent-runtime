# WORKSPACE-ISSUE-054 — Run submission admission retained the legacy Groupware-only Session guard

## Status

FIX_IMPLEMENTED_LIVE_RERUN_REQUIRED

## Actual Windows evidence

The R10C focused cross-domain Live run failed before any Run was created:

```text
failure_stage=execute_establish-employee-focus
CLI returncode=0
CLI one_request_completed=false
Runtime run_count=0
Product error=[RUN_SUBMISSION_INVALID] Root Agent must declare exactly the Groupware read Sub-agent
```

The preceding R10B Session Agent/runtime binding mismatch was no longer present, proving STEP094R1's unified
Session root had taken effect. Admission was instead rejected by a second, older owner boundary.

## Root cause

`RunSubmissionBoundaryService.preflight()` still used `GroupwareSessionDelegationCatalog` when the submitted
Agent was `organization-assistant-session-agent`. That catalog is the historical single-domain STEP087 contract
and requires the root to declare exactly one child: `groupware-read-agent`.

STEP094R1 intentionally changed the current canonical root to own two stateless children:

```text
organization-assistant-session-agent
  ├─ groupware-read-agent
  └─ organization-context-read-agent
```

Runtime binding and OpenAI gateway already used `CrossDomainSessionDelegationCatalog`, but Run submission
admission did not. The runtime was therefore internally inconsistent across owner boundaries.

## Canonical correction

STEP094R2 changes the actual admission owner. For the unified root, submission preflight now resolves
`CrossDomainSessionDelegationCatalog`, parses the immutable Product routing context already embedded in the
model request, selects at most one domain target, and admits only that target's MCP server for delegated access.

```text
immutable Product routing context
  -> CrossDomainSessionDelegationCatalog
  -> target_for_request()
  -> exactly one of:
       organization-context-read
       groupware-read
  -> delegated MCP access validation
  -> strict Session binding validation
```

The historical `GroupwareSessionDelegationCatalog` source remains retained for historical evidence and old
single-domain semantics, but it is no longer referenced by current runtime binding, gateway, or submission
admission paths.

## Explicitly forbidden non-fixes

The correction does not add or use:

- Agent aliases;
- Session aliases;
- display-name or label fallback;
- Tool fallback;
- route fallback;
- compatibility shim around the old catalog;
- retry with another Agent;
- Session-ID switching;
- focus copying between Sessions;
- weakening of `SessionRuntime.validate_binding()`.
