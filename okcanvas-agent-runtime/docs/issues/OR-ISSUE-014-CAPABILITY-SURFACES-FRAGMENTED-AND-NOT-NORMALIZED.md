# OR-ISSUE-014 — Agent capability surfaces were fragmented and not normalized

## Status

`FIX_IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

## Exact symptom

The product supported Function Tools, hosted Web Search, Product-owned Skills, native Handoffs, Agent-as-Tool, bounded orchestration children, MCP servers, Guardrails, workspace access, input adapters, and SQLite Sessions. Each Agent definition represented these as separate parallel fields:

```text
tools
hosted_tools
mcp_servers
skills
handoffs
agent_tools
orchestration_children
guardrails
workspace_access
input_mode
session_mode
```

There was no single immutable topology answering which capabilities an Agent owns, how each capability is invoked, which SDK surface it maps to, whether it is eagerly or deferred loaded, whether Tool Search may discover it, whether direct or programmatic callers are allowed, and which definition SHA is bound into execution.

The pinned `openai-agents-python-0.19.0/examples` tree contained Tool Search, Programmatic Tool Calling, Shell Skills, MCP, sub-Agent, Guardrail, workspace and hosted Tool examples, but the product had no machine-readable inventory linking those examples to current, structural-only, deferred or rejected product decisions.

## Code-confirmed root cause

`AgentDefinition` accumulated one field per adopted feature and `AgentDefinitionCatalog` accumulated STEP-specific composition branches. `AgentRuntimeBinding` bound each family independently. The product's `tools` field meant only Product Function Tools, while the SDK `Agent.tools` union also includes hosted Tools, Shell, Apply Patch, Code Interpreter, Tool Search, Programmatic Tool Calling and Agent-as-Tool wrappers. The same word therefore described different domains.

No capability discovery policy existed to predeclare namespaces, eager/deferred loading, Tool Search eligibility or allowed callers while keeping those runtimes disabled.

## Impact

Adding Tool Search, Hosted MCP discovery, Code Interpreter, new Skills or another sub-Agent surface would require another parallel field and another set of one-off conditions. It would be easy to accidentally expose Shell-based SDK Skills as equivalent to the current instruction-only Product Skill, or classify `Agent.mcp_servers` as Tool Search eligible even though SDK 0.19.0 Tool Search only searches deferred Function Tools and deferred Hosted MCP Tools.

Execution fingerprints could not prove the complete capability topology selected for an Agent.

## Fix

STEP080 adds:

- `CapabilityFamily`, `CapabilityBinding`, `CapabilityNamespace` and `AgentCapabilityTopology` immutable contracts;
- `CapabilityDiscoveryPolicyCatalog` with structure-only Tool Search and Programmatic Tool Calling metadata;
- `AgentCapabilityTopologyCatalog`, normalizing every existing Agent surface without changing execution;
- `CapabilityFoundationCatalog`, aggregating all 27 Agent topologies, 33 active bindings, family/kind counts, discovery policy and SDK example inventory into one topology root SHA;
- a hash-pinned 30-record inventory of exact OpenAI Agents 0.19.0 examples;
- Agent public catalog and runtime binding integration;
- Service capability metadata for topology/discovery/example inventory;
- parser, launcher, deterministic and Windows-live gates for STEP080.

## Preserved boundaries

STEP080 does not instantiate `ToolSearchTool` or `ProgrammaticToolCallingTool`, does not use `defer_loading=True`, does not allow programmatic callers, does not enable Shell, Apply Patch, Code Interpreter, File Search, Computer Use or SDK Shell Skills, and does not import executable code from `reference/upstream`.

Current Product Skill remains immutable instructions plus declared static resources. Current MCP server bindings remain separate `Agent.mcp_servers` entries and are not falsely declared Tool Search eligible.

## Evidence and recurrence gates

- `tests/test_step080_product_owned_capability_topology_and_tool_discovery_foundation.py`
- `tests/test_step080_windows_entrypoint_capability_topology_registration.py`
- `scripts/run_step080_acceptance.py`
- `scripts/run_step080_live_acceptance.py`
- `specs/capabilities/tool-discovery-policy.json`
- `specs/capabilities/examples/openai-agents-python-0.19.0.json`

The issue closes only after the packaged STEP080 ZIP passes deterministic and Windows live acceptance.
