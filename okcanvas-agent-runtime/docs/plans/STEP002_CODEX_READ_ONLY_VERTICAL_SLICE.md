# STEP002_CODEX_READ_ONLY_VERTICAL_SLICE

## Objective
Connect the inspected official `openai-agents==0.19.0` experimental `codex_tool` contract to a controlled repository analysis flow and prove that the runtime fails closed when the SDK, Codex CLI, models, or API key are unavailable.

## Current code evidence

- Upstream implementation: `reference/upstream/openai-agents-python-0.19.0/src/agents/extensions/experimental/codex/`.
- Upstream examples: `examples/tools/codex.py` and `codex_same_thread.py`.
- STEP001 had a tool-free Agent only.

## In scope

- rename declarative roots to `specs/agents`, `specs/mcp`, and `specs/tools`;
- one `codex_engineer` tool using official `codex_tool`;
- Codex sandbox mode `read-only`;
- web search disabled and workspace-write network access requested off;
- explicit Codex CLI and SDK readiness;
- explicit controlled-workspace confirmation and Git requirement;
- symbolic-link rejection;
- external Evidence-path enforcement;
- subprocess environment allowlist;
- disposable known-defect fixture;
- before/after source tree SHA-256;
- canonical Codex JSONL event journal;
- explicit thread state file and resume;
- required relevant-file acceptance;
- live acceptance script for a connected environment.

## Non-scope

Workspace write, MCP, arbitrary shell exposure, external repositories, Windows validation, PR/commit automation, deployment, and production data access.

## Contracts affected

- `okcanvas-codex-readonly-run-v1` envelope;
- `CodexReadOnlyResult` structured output;
- `okcanvas-codex-thread-v1` thread state;
- `specs/agents/codex-readonly-agent`;
- `specs/tools/codex/policy.yaml`.

## Validation commands

```bash
python -m compileall -q src scripts tests
pytest -q
PYTHONPATH=src python scripts/verify_reference.py
PYTHONPATH=src python scripts/verify_codex_fixture.py
PYTHONPATH=src python -m okcanvas_agent_runtime info --pretty
PYTHONPATH=src python -m okcanvas_agent_runtime codex-doctor --pretty
```

Connected live acceptance:

```bash
export OPENAI_API_KEY=...
export OKCANVAS_AGENT_MODEL=...
export OKCANVAS_CODEX_MODEL=...
export OKCANVAS_STEP002_LIVE_ACCEPTANCE=1
PYTHONPATH=src python scripts/run_step002_live_acceptance.py
```

## Acceptance criteria

### Deterministic implementation acceptance

- old root `agents`, `mcp`, and `tools` absent;
- 4/4 reference snapshots unchanged;
- fixture defect reproduced for the expected assertion;
- official SDK contract test double verifies read-only Codex options;
- workspace mutation is detected and fails closed;
- file-change, web-search, and MCP events are rejected;
- missing thread, event, command, or verified-file Evidence is rejected;
- required relevant files are enforced;
- JSONL event ordering and SHA retained;
- thread state is persisted and deterministic resume is tested.

### Live acceptance

- exact SDK installed;
- Codex CLI version retained;
- first run discovers `src/inventory/pricing.py` and `tests/test_pricing.py` without paths in the prompt;
- second run resumes the same Codex thread;
- event files contain actual Codex CLI events;
- source tree hash remains unchanged for both runs;
- the controlled fixture contains no symbolic links and Evidence files remain outside it.

## Failure and recovery

- readiness failures occur before event-file creation or model execution;
- any source mutation returns `WORKSPACE_MUTATED` and no completion claim;
- a thread state whose workspace hash differs is rejected;
- live acceptance remains pending until executed in a connected environment.

## Artifact

`okcanvas-agent-runtime-step002-codex-readonly-implementation.zip`
