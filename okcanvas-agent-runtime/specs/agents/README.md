# Agent Definitions

This is a declarative area, not a Python package. Agent instructions, policies, output schemas, and evaluations live here. Executable builders live under `src/okcanvas_agent_runtime/agents/`.

Canonical generic definitions currently include coding analysis, immutable reference research, controlled local text metrics, and the read-only store replenishment review Agent.

Agent definitions may declare closed `handoffs` and `agent_tools` target IDs plus `workspace_access`. STEP040 accepts only `workspace_access=none`; these graph fields are Runtime-bound and do not by themselves enable child execution. A future child invocation may only target a definition declared by its parent.

## Session approval Agent

`session-approval-agent` is the only STEP046 Session+Tool composition. It uses `sqlite-v1`, exactly one `ALWAYS` Tool, no child/MCP/Guardrail/workspace capability, and resolves through `sqlite-session-approval-execution-v1`.

## STEP048 Session Guardrail Agent

`session-guardrail-language-agent` declares `session_mode=sqlite-v1`, `block-input-marker`, and `block-output-marker`. It has no Tool, MCP, child Agent, Handoff, workspace or external capability.

## STEP062 bounded orchestration Agents

`bounded-orchestration-manager-agent` is a logical Product-owned root. It declares exactly
`bounded-orchestration-architecture-agent` and `bounded-orchestration-risk-agent` through
`orchestration_children`. The root performs no SDK model call. Both children are terminal
language-only Agents with `CodingAgentResult` output, Session disabled, workspace `none`, and no
Tool, MCP, Handoff, Agent-as-Tool, Guardrail or nested orchestration capability. Successful child
outputs are aggregated by Product code into `BoundedOrchestrationResult` in declaration order.

## Product-owned Skill binding

Agent definitions may declare `skills`. Product Skill V1 permits at most one immutable server-owned
Skill per Agent. The closed Skill catalog verifies Agent allowlist, input mode, output contract and
required capability subsets. A Skill cannot add permissions. The first binding is
`skill-document-review-agent` → `document-review-v1`.
