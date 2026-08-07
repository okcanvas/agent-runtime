# WORKSPACE STEP005R1 — Groupware Acceptance Pattern Alignment

## Identity

```text
WORKSPACE_STEP005R1_GROUPWARE_ACCEPTANCE_PATTERN_ALIGNMENT
Version: 0.5.1
Parent: WORKSPACE_STEP005_ORGANIZATION_CONTEXT_CONNECTOR_AND_CONSTRUCTION_GUIDE_FOUNDATION / 0.5.0
```

## Trigger

Actual Windows STEP005 completed `18/23`. The Example passed, Connector pytest passed, and Workspace manifest drift was empty. Failures were limited to acceptance execution:

- standard `compileall` could not create an overlong `.pyc` path under the combined Workspace pycache overlay and fully mirrored temp project path;
- the Connector-local optional integration invoked literal `npm` and `node`, producing Windows `WinError 2` even though the Workspace had already resolved `npm.cmd` and `node.exe`.

## Governing correction

Do not create a second Organization Context harness. Reuse the Windows-live accepted Groupware Workspace E2E pattern.

```text
Workspace executable resolution
→ short isolated Connector/Example copies
→ Workspace-owned E2E runner
→ actual Connector MCP
→ actual Example REST API
```

## Scope

- no Runtime product source changes;
- no Organization Context API semantic changes;
- no MCP Tool changes;
- Connector and Example versions advance to `0.1.1` for acceptance/project-pattern alignment;
- standard `compileall` retained;
- Example gains Groupware-equivalent source packaging and immutable evidence.

## Deferred

Runtime pre-routing, Agent grounding, revision-aware Runtime cache, and replacement of STEP084 local JSON remain deferred.
