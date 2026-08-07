# STEP059 Code and Reference Audit

## Audited baseline

The audit began from the packaged STEP058 ZIP after the user reported the complete Windows 18/18
acceptance. The required handoff set and immutable `openai-agents-python-0.19.0` Reference were read
before selecting the next scope.

## Findings

1. The Runtime already had governed Function Tool construction, immutable Tool definitions,
   non-persistence of raw Tool arguments/results, exact confirmation, lifecycle Events and Artifact
   validation.
2. The Node CLI intentionally admitted only approval-free, read-only isolated Tool Agents, but the
   existing safe Tool had filesystem access `none`.
3. No product-facing Agent could inspect the configured source project. The historical Codex paths
   and immutable References are not an appropriate general project-reading API.
4. Introducing Shell, generic filesystem primitives or Sandbox at this point would widen authority
   before the actual read-only coding need was measured.

## Implemented boundary

### Product-owned scanner

`src/okcanvas_agent_runtime/workspace/read_only_project.py` owns traversal, text decoding, query
ranking, excerpts and snapshot identity. It uses `os.walk(..., followlinks=False)`, rejects a symlink
root, filters symlink entries and returns only repository-relative paths.

Excluded directory names include `.git`, `.venv`, `node_modules`, generated output, test caches,
`.local` and `reference`. Binary/NUL content and over-limit files are skipped.

### Function Tool

`project_readonly_inspect_v1` uses the existing opaque execution-id input. The protected user request
is supplied by Product code as the inspection query. Public capability is exactly:

- `approval_mode=NEVER`;
- `read_only=true`;
- `filesystem_access=read-only`;
- `network_access=none`;
- `shell_access=none`;
- arguments and results not persisted in Events.

The generic OpenAI gateway passes the server-owned configured root only to this exact factory.

### Agent and CLI

`project-readonly-coding-agent` has exactly one Tool and no Session, MCP, Handoff, Agent-as-Tool,
Guardrail or workspace mutation capability. Its instructions require Tool evidence and relative
path/line citations for confirmed findings.

The Node CLI accepts this exact read-only filesystem Tool while continuing to reject general
filesystem-capable Tools. Normal output renders at most three bounded evidence strings per finding,
removes line breaks and never renders Tool excerpts automatically.

### Environment

`OKCANVAS_READONLY_WORKSPACE_ROOT` is a shared allowlisted `.env.local` key. Windows pre-launch
validation requires an existing directory. `app_from_environment()` passes the value into the
default gateway. The canonical `.env.local.example` sets `.` and documents restart after changing
projects.

## Non-claims

STEP059 does not provide a Sandbox, security against a malicious local repository, filesystem write,
Shell, Git process, network, arbitrary file path API, multiple simultaneous project roots, Session
memory for the project Agent or recursive/parallel Sub Agents.

## Deterministic evidence

The first acceptance run found one UI defect: structured finding evidence existed in the Artifact but
the answer-first renderer omitted it. The renderer was corrected to display bounded relative
locations without Tool excerpts.

The corrected acceptance passed 16/16 with `src/router.py:1-3`, three files and 178 bytes considered,
no excluded dependency sentinel, no workspace mutation, exact Product counts `1/1/1/1/12/1/0`, zero
payload files, unchanged References and cleanup completed once.
