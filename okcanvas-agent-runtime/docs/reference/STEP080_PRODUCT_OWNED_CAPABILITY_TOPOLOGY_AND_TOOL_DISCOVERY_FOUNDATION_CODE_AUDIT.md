# STEP080 code audit — Product-owned capability topology and Tool discovery foundation

## Audited baseline

`STEP079A_WINDOWS_ENTRYPOINT_COMMAND_REGISTRATION_FIX`, version `2.59.1`, Windows live accepted 57/57.

## Existing product capability surfaces

Direct source audit found 27 Agent definitions and these active declarations:

```text
Function Tool declarations: 7
hosted Web Search declarations: 1
MCP declarations: 2
Product Skill declarations: 1
native Handoff declarations: 2
Agent-as-Tool declarations: 2
orchestration child declarations: 2
Guardrail declarations: 6
SQLite Session bindings: 7
local attachment input bindings: 2
read-only Sandbox workspace bindings: 1
```

After normalization these become 33 active bindings across eight families: `tool`, `skill`, `sub-agent`, `mcp`, `guardrail`, `workspace`, `input`, and `session`.

## SDK 0.19.0 audit

The pinned SDK Tool union contains Function, hosted search, File Search, Computer, Hosted MCP, Custom, Shell, Apply Patch, Local Shell, Image Generation, Code Interpreter, Tool Search and Programmatic Tool Calling surfaces.

The pinned Tool Search example proves:

```text
ToolSearchTool()
tool_namespace(...)
@tool(defer_loading=True)
```

The pinned Programmatic Tool Calling example proves:

```text
ProgrammaticToolCallingTool()
@tool(allowed_callers=["programmatic"])
```

The pinned Shell Skill examples prove that SDK Skills are mounted into `ShellTool` local/container environments and may contain executable scripts. They are not equivalent to the current Product Skill contract.

SDK 0.19.0 Tool Search eligibility is therefore represented structurally as follows:

- Product Function Tools: eligible future surface, currently eager/direct-only;
- current MCP servers: not eligible because they use `Agent.mcp_servers`, not deferred `HostedMCPTool`;
- Product Skill: not a Tool Search surface;
- Agent-as-Tool: kept as sub-Agent topology, not activated for deferred discovery;
- hosted Web Search: active hosted Tool but not deferred;
- Shell/Code Interpreter/File Search/etc.: inventory only.

## Implemented code

```text
src/okcanvas_agent_runtime/capabilities/models.py
src/okcanvas_agent_runtime/capabilities/policy.py
src/okcanvas_agent_runtime/capabilities/examples.py
src/okcanvas_agent_runtime/capabilities/catalog.py
specs/capabilities/tool-discovery-policy.json
specs/capabilities/examples/openai-agents-python-0.19.0.json
```

`AgentDefinition.to_public_dict()` exposes the normalized topology. `AgentRuntimeBinding` includes the topology, capability runtime source SHA and SDK example inventory SHA in its fingerprint. `CapabilityFoundationCatalog` creates one package topology root SHA from all Agent topologies, family/kind counts, policy and inventory.

The authenticated Service capabilities response exposes only compact metadata and hashes, not raw upstream source.

## Security and authority audit

The policy loader rejects `tool_search.runtime_enabled=true` and `programmatic_tool_calling.runtime_enabled=true`. The topology catalog rejects active deferred bindings and any programmatic caller. No source file imports from `reference/upstream`; example records are exact hash-verified evidence only.

No existing execution adapter was changed to instantiate a new Tool. Model, Tool, Docker, Sandbox, Skill and MCP execution behavior is unchanged.
