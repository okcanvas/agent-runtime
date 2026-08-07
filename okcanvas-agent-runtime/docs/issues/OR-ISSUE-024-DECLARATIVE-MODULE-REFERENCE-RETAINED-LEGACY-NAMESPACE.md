# OR-ISSUE-024 — Declarative module reference retained a legacy namespace

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

`MCPServerCatalog` resolved the Product-owned reference server definition with:

```text
okcanvas_agent_runtime.mcp_servers.reference_catalog
```

while the implementation had been physically moved to:

```text
okcanvas_agent_runtime.adapters.mcp.servers.reference_catalog
```

The MCP definition regression failed even though a compatibility alias made the historical import path executable.

## Code-confirmed root cause

The Python relocation and alias manifests covered source modules, but the executable JSON definition in `specs/mcp/servers/reference-catalog/server.json` was not included in the namespace rewrite. The catalog regex also continued to authorize only the pre-STEP081 namespace.

## Impact

Runtime-selected MCP server identity remained bound to a compatibility alias instead of its canonical Adapter owner. Removing aliases in a later cleanup could break server launch, and static Python import checks could not detect the stale declarative reference.

## Fix

- changed the MCP server definition to the canonical Adapter module;
- changed the catalog allowlist regex to the canonical Product-owned MCP Adapter namespace;
- retained the old namespace only as a compatibility import alias.

## Detailed evidence

`tests/test_mcp_definition_catalog.py` and the affected 40–59 regression chunk pass after the correction.

## Recurrence-prevention gate

`declarative_module_references_current` reads every local MCP server definition and requires each declared Python module to exist in the current canonical module inventory.
