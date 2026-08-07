# OR-ISSUE-092 — STEP086 declarative Agent boundary overclaimed external provider implementation

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_PENDING`

## Discovered in

Post-STEP086 code review after Windows deterministic acceptance

## Failure

STEP086 implemented a Product-owned declarative `groupware-read-agent`, routing, readiness, delegated identity and a V3 remote MCP client declaration. The completion summary described that boundary as a completed Groupware read Agent even though the Runtime contained no actual Groupware MCP server, no Groupware API adapter and no live external Tool call evidence.

## Root cause

The Product had no explicit ownership/deployment contract distinguishing four different things:

1. an internal declarative Sub-agent definition;
2. an internal MCP client declaration;
3. an internal deterministic provider-contract fixture;
4. the actual external organization connector service.

The boolean `groupware_read_only_vertical_implemented=True` compressed these distinct states into one overbroad claim.

## Correction

- `specs/groupware/deployment-boundary.json` fixes the Sub-agent and MCP client declaration inside the Runtime while placing the actual provider in an external connector service.
- `specs/groupware/read-provider-contract.json` defines the external Tool and delegated-identity contract without claiming an implementation.
- deterministic fixtures remain internal but are explicitly non-production.
- RuntimeInfo now reports `SUBAGENT_AND_CLIENT_BOUNDARY_ONLY`, sets the old full-vertical claim false, and exposes provider-implemented/live-verified as false.
- future write capability is reserved for a separate Agent, MCP server and credential boundary.

## Recurrence gate

- `tests/test_step086r1_groupware_subagent_and_external_mcp_boundary_alignment.py`
- `scripts/validate_step086r1_groupware_boundaries.py`
- STEP086R1 integrated and Fresh ZIP acceptance
