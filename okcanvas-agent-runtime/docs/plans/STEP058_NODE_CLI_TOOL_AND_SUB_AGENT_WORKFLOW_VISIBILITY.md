# STEP058 — Node CLI Tool and Sub Agent Workflow Visibility

## State

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

## Goal

Expose the Runtime's already accepted read-only Function Tool, native Handoff and Agent-as-Tool paths through the persistent Node.js/TypeScript CLI. Add safe progress and invocation visibility without adding a new orchestration engine or expanding execution authority.

## Supported paths

- `local-text-fingerprint-agent`: one approval-free read-only Function Tool.
- `handoff-triage-agent` and `session-handoff-triage-agent`: one native Handoff edge.
- `agent-tool-manager-agent` and `session-agent-tool-manager-agent`: one Agent-as-Tool child edge.
- Existing text-only Agents remain supported.

## Excluded paths

- `approval_mode=ALWAYS` Tools and approval decisions;
- MCP and remote transports;
- Guardrails;
- workspace, file, Shell, network and Sandbox;
- mixed Tool/Handoff/Agent-as-Tool graphs;
- multiple children, depth greater than one and parallel execution.

## Product behavior

1. `/agents` and selection menus show Session mode and capability type.
2. Normal mode displays bounded progress for Tool, Handoff and Sub Agent lifecycle events.
3. Handoff and Agent-as-Tool Runs show the terminal invocation tree after the answer.
4. `/invocations` displays the last Product invocation ledger on demand.
5. Debug mode keeps the complete safe persisted SSE view.
6. Raw Tool arguments/results and child content are never rendered or persisted by the CLI.

## Acceptance

One Node process runs exactly three governed requests through the three supported capability families. Expected final Product counts are Task/Run/Submission/Invocation/Event/Artifact/Evaluation `3/3/3/5/35/3/0`, no successful protected payload remains, References are unchanged and cleanup completes once.
