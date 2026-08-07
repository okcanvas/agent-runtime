# STEP080 — Product-owned capability topology and Tool discovery foundation

## Identity

```text
STEP080_PRODUCT_OWNED_CAPABILITY_TOPOLOGY_AND_TOOL_DISCOVERY_FOUNDATION
version: 2.60.0
```

## Objective

Create one immutable extension architecture for current and future Tools, Skills, sub-Agents, MCP, Guardrails, workspace, input and Session capabilities. Compare that architecture directly with the pinned `openai-agents-python-0.19.0` SDK and examples while preserving all current runtime authority.

## Product contract

Each active Agent capability is normalized into:

```text
family
kind
capability_id
version
invocation_mode
sdk_surface
activation
loading
namespace_id
tool_search_eligible
direct_call_allowed
programmatic_call_allowed
read_only
approval_mode
definition_sha256
```

A package-wide foundation binds:

```text
27 Agent topologies
33 active bindings
8 capability families
30 exact SDK example records
one discovery-policy SHA
one SDK-example inventory SHA
one topology-root SHA
```

## Tool Search preparation

Structure-only metadata is introduced for:

- namespaces;
- eager versus deferred loading;
- Tool Search eligible surface kinds;
- direct versus programmatic callers;
- execution location and upper bounds.

Runtime Tool Search remains disabled. Existing Function Tools remain eager and direct-only. Current `Agent.mcp_servers` remain in the MCP family and are not misrepresented as deferred Hosted MCP Tools.

## Skills

Current Product-owned Skill remains an immutable instruction/static-resource package. SDK Shell Skill examples are inventoried as a distinct executable capability class and remain inactive because they require Shell/container authority.

## SDK example inventory

The product records the exact relative path and SHA-256 of relevant 0.19.0 examples for:

- Tool Search and Programmatic Tool Calling;
- hosted and local Tool families;
- Skills;
- sub-Agents, Handoffs and Agent-as-Tool;
- MCP;
- Guardrails;
- workspace/sandbox composition.

The inventory reads pinned files as evidence and never imports upstream executable code.

## Non-goals

- no `ToolSearchTool` activation;
- no `ProgrammaticToolCallingTool` activation;
- no deferred Function Tool loading;
- no model-generated program execution;
- no Shell, Apply Patch, Computer Use or Code Interpreter;
- no hosted File Search or Vector Store lifecycle;
- no user-installed Skill or Skill execution;
- no change to existing Agent behavior, model calls or Tool calls.

## Acceptance

Deterministic acceptance validates topology normalization, exact SDK examples, runtime binding, Service metadata, runtime-disabled discovery mechanisms, Windows command registration, full regressions, packaging and reference integrity.

Windows live acceptance reruns the accepted immutable snapshot workflow and adds capability topology/foundation/discovery/example-inventory binding checks. Expected final total: 62 checks.
