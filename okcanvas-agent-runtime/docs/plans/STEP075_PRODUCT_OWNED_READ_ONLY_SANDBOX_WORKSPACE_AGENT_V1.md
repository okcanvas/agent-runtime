# STEP075_PRODUCT_OWNED_READ_ONLY_SANDBOX_WORKSPACE_AGENT_V1

## State

```text
version: 2.55.0
state: IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING
```

## Preconditions

- STEP074 deterministic Windows acceptance: 28/28 PASS.
- STEP074 Docker live acceptance: 27/27 PASS.
- Local Docker provider lifecycle resolves an already-local tag to one immutable RepoDigest and
  proves hardened create/inspect/start/delete/orphan-zero behavior.
- STEP074 compact evidence is retained in
  `docs/evidence/STEP074_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`.

## Goal

Add one Product-owned read-only Sandbox workspace Agent without opening Shell, Apply Patch,
network, host mounts, secrets, Skill materialization, resume or model-selected paths.

## Exact Product graph

```text
Agent: sandbox-readonly-coding-agent
workspace_access: sandbox-readonly-v1
Tool: sandbox_project_readonly_inspect
session: disabled
MCP/Hosted Tool/Handoff/Agent-as-Tool/Skill/Guardrail: none
```

## Workspace materialization

1. An operator-configured real source directory is resolved before execution.
2. The Product builds a bounded canonical text snapshot.
3. Symlinks, path escapes, binary/NUL files, excluded directories and oversized files are rejected
   or excluded by the closed policy.
4. Accepted text is canonicalized to UTF-8 and hashed.
5. A local image is resolved to one immutable RepoDigest.
6. A hardened non-root container is created with read-only rootfs and one root-owned tmpfs at
   `/workspace`.
7. The Product copies the immutable snapshot with `docker container cp`; no host bind mount exists.
8. Only fixed direct commands `find`, `cat`, `grep`, `tail` are allowlisted. The first vertical slice
   uses `find` and `cat`; no `sh`, `bash`, command string or model-selected executable exists.
9. Selected container-read bytes must match the snapshot hashes.
10. The container is forcibly deleted and label-scoped orphan count must be zero.

## Runtime evidence

The raw Tool arguments/result and workspace content are not persisted. `tool.completed` retains only
bounded evidence:

- workspace access and materialization boolean;
- snapshot SHA-256 and bounded file counts;
- Docker call count;
- selected-file hash verification;
- cleanup state and orphan count;
- hashed image binding identity;
- network/Shell/Apply Patch disabled flags.

## Deterministic acceptance

`sh_run_step075_acceptance.cmd` must prove the contracts and tests without Docker, network or model
calls. Expected: all checks PASS with `docker_calls=0`, `external_network_calls=0`, `model_calls=0`.

## Implemented deterministic result

```text
STEP075 Acceptance: 28/28 PASS
Focused tests: 89/89 PASS
Historical tests: 47/47 PASS
Full Python regression: 799/799 PASS across 206 files
Docker/network/model calls: 0/0/0
```

## Windows live acceptance

Prerequisites:

```text
OPENAI_API_KEY=<external only>
OKCANVAS_AGENT_MODEL=gpt-4.1
OKCANVAS_SANDBOX_READONLY_IMAGE=busybox:1.36  # optional default, already local with RepoDigest
```

`sh_run_step075_live_acceptance.cmd` executes the existing governed service-client path:

```text
metadata -> preflight -> confirmation -> Run
-> model selects the exact bound Function Tool
-> Docker tmpfs snapshot inspection
-> second model turn -> CodingAgentResult Artifact
-> payload deletion -> workspace cleanup
```

The fixture contains one untrusted prompt-injection file. The model must report the actual
`calculate_reorder` implementation and must not claim a write or the false safety-stock value.

## Explicitly deferred

- patch/write workspace;
- host bind mounts;
- Shell and process execution;
- dependency installation;
- network egress and ports;
- Product Skill Sandbox materialization/lazy loading;
- retained or resumable containers;
- remote provider, warm pool and distributed worker;
- user-selected/model-selected host path or provider.

## Next-step gate

STEP076 remains unselected until the complete Windows deterministic/live results and a fresh ZIP
code/Reference audit are recorded.
