# STEP059 — Bounded Project Read-only Coding Workflow

## Baseline

- Project: `okcanvas-agent-runtime`
- Version: `2.39.0`
- STEP: `STEP059_BOUNDED_PROJECT_READONLY_CODING_WORKFLOW`
- State: `IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

## Why this STEP

STEP058 proved that the persistent Node.js/TypeScript CLI can select and visibly execute the
Runtime's existing isolated read-only Tool, Handoff and Agent-as-Tool paths. Manual use still could
not answer questions about an actual project because every exposed Tool had filesystem access
`none`.

The next product slice is therefore one real coding workflow with bounded read-only project
evidence. This is intentionally not a general filesystem API and not a Sandbox.

## Product scope

1. Add one Product-owned Function Tool, `project_readonly_inspect`.
2. Read exactly one server-configured root from `OKCANVAS_READONLY_WORKSPACE_ROOT`.
3. Add one isolated Agent, `project-readonly-coding-agent`, with exactly that Tool.
4. Permit the Node CLI to select the Agent and show bounded Tool progress.
5. Render confirmed finding evidence as repository-relative `path:line-range` locations.
6. Preserve the existing governed preflight, exact confirmation, persisted SSE, Artifact and
   Runtime-binding boundaries.

## Bounded inspection contract

- maximum candidate text files: `3,000`;
- maximum aggregate bytes: `32 MiB`;
- maximum bytes per file: `512 KiB`;
- maximum evidence files: `12`;
- maximum excerpt: `4,000` characters and `40` lines per evidence item;
- text allowlist only;
- no symlink root or symlink traversal;
- dependency, generated, local-state and immutable Reference directories excluded;
- returned paths are repository-relative only.

## Explicit exclusions

- file creation, modification, deletion or rename;
- arbitrary path selection by the model;
- Shell or process execution;
- Git commands;
- network or web access;
- package-manager execution;
- MCP, Approval, Handoff, Agent-as-Tool, Guardrail or Session composition;
- multiple workspaces in one API process;
- Sandbox or hostile-code isolation.

Changing the inspected project requires changing `OKCANVAS_READONLY_WORKSPACE_ROOT` and restarting
the Control API.

## Acceptance

A real loopback Control API and one Node CLI process inspect a fixture project. The Tool must locate
`src/router.py`, display only relative path/line evidence, exclude a dependency sentinel under
`node_modules`, leave every fixture byte unchanged, create no Evaluation by default, delete the
successful protected payload, preserve References and clean up once.

Expected final Product counts:

`Task/Run/Submission/Invocation/Event/Artifact/Evaluation = 1/1/1/1/12/1/0`.

STEP060 must not be selected before complete Windows STEP059 acceptance is reported.
