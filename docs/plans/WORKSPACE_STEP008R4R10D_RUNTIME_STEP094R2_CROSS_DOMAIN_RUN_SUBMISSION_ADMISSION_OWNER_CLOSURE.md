# WORKSPACE STEP008R4R10D / Runtime STEP094R2

Workspace version: `0.8.4-r10d`  
Runtime version: `2.78.2`

## Purpose

Close the actual R10C Windows admission failure without aliases or fallbacks. The cross-domain Session graph
was already canonical in STEP094R1, but governed Run submission still used the historical Groupware-only
composition owner.

## Change

`RunSubmissionBoundaryService.preflight()` now uses the same `CrossDomainSessionDelegationCatalog` as Runtime
binding and the OpenAI gateway. It reads the immutable Product routing context and adds only the selected
child's MCP server to submission delegated-access validation.

## Required invariants

1. One long-lived `organization-assistant-session-agent` owns both read-only stateless children.
2. Runtime binding SHA contains both children and both exact MCP owners.
3. One Turn selects at most one delegated read domain.
4. Submission admission, gateway execution and Runtime binding use the same cross-domain catalog.
5. Session binding remains strict.
6. Stable Organization focus remains the only content-reference authority for Groupware cross-domain reads.
7. No helper alias, label fallback, Tool fallback, route fallback or Session switching is permitted.

## Acceptance status

Implementation and static/Fresh validation only. R10D focused Windows cross-domain Live is required before
promotion. The existing launcher remains:

```bat
sh_run_workspace_step008r4r10_cross_domain_live_acceptance.cmd
```

## Current-source manifest SOT repair

Final R10D validation also found that the Groupware Connector/Example **current source inventory** manifests still recorded STEP001R1/0.1.1 hashes even though the actual projects had already advanced in STEP094 to STEP002/0.2.0. R10C→R10D project trees were byte-identical, proving this was inherited manifest drift rather than an R10D Groupware source change. R10D regenerates those two current manifests from the actual STEP002 trees. Historical `accepted-parent-artifacts.json` and STEP001R1 acceptance evidence remain unchanged. See `WORKSPACE-ISSUE-055`.
