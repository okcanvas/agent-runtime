# Product-owned Sandbox Runtime V1

## Current status

`STEP075_PRODUCT_OWNED_READ_ONLY_SANDBOX_WORKSPACE_AGENT_V1` activates the first narrowly governed
Agent Sandbox execution path. STEP073 established the immutable policy/provider and Runtime-binding
foundation. STEP074 proved the hardened local-Docker lifecycle on Windows. STEP075 adds exactly one
Product-owned read-only workspace Agent and one Product-owned read-only Function Tool.

This contract does not enable general-purpose Sandbox access, Shell, Apply Patch, network, host
mounts, secrets, Skill materialization, retained containers, resume, snapshots, remote providers or
model-selected paths/providers.

## Authority

The Product-owned Sandbox catalog is authoritative. OpenAI Agents SDK Sandbox classes are retained
reference material only. No prompt, model response, Agent definition, Skill, service client or user
input may select or expand a provider, host path, image, mount, network policy, executable,
capability, quota or secret.

## Accepted foundation history

- STEP073: immutable Product policy/provider identities, service metadata and Runtime binding;
  provider execution disabled and all Agents `workspace_access=none`.
- STEP074: Product-owned hardened local-Docker provider lifecycle, immutable local RepoDigest,
  `--pull=never`, network none, no mounts/ports/secrets, non-root, read-only rootfs, cap-drop ALL,
  no-new-privileges, bounded resources, forced deletion and orphan-zero. Windows Docker live
  acceptance is closed.
- STEP075: one exact read-only Agent graph and bounded canonical workspace snapshot materialized to
  container-owned tmpfs.

## Exact active STEP075 graph

```text
Agent: sandbox-readonly-coding-agent
workspace_access: sandbox-readonly-v1
Tool: sandbox_project_readonly_inspect
output: CodingAgentResult
```

The other 26 Product Agents remain `workspace_access=none`. `sandbox-patch-v1` and
`sandbox-shell-v1` remain declared names only and are not active capabilities.

## Source snapshot contract

- The source root is operator-configured server state; the model and service client cannot choose a
  host path.
- The Product walks the source tree without following symlinks and closes path escape.
- VCS directories, dependencies, virtual environments, build outputs, caches, `.local`, and
  `/reference` are excluded by policy.
- Binary/NUL files and files outside the bounded text contract are excluded or rejected.
- Limits are 3,000 accepted files, 32 MiB total accepted bytes and 512 KiB per file.
- Accepted UTF-8, UTF-8-SIG and CP949 text is decoded and normalized to exact UTF-8 before hashing
  and materialization.
- The canonical snapshot records sorted relative paths, per-file SHA-256 and one aggregate snapshot
  SHA-256.

## Container workspace contract

- The configured local image must already exist and resolve to exactly one immutable RepoDigest.
- Runtime image pull is forbidden.
- The source directory is never bind-mounted.
- A hardened non-root container is created with read-only rootfs and a Product-owned tmpfs mounted
  at `/workspace` with `noexec,nosuid,nodev` and a 32 MiB bound.
- The Product streams a canonical deterministic tar archive through fixed `docker container exec --interactive --user 0:0 ... tar` stdin into the container-owned
  tmpfs.
- Network mode is `none`; ports, network attachments, host/remote/Docker-socket mounts, container
  environment and secrets are absent.
- Privileged mode and cap-add are forbidden; cap-drop ALL and no-new-privileges are mandatory.
- Memory, CPU, PID, timeout and captured-output bounds remain Product-owned.
- The long-lived container command is Product-fixed `tail -f /dev/null`; it is not selected by the
  model or user.

## Read-only command contract

The Product code owns the exact direct-exec allowlist:

```text
find
cat
grep
tail
```

STEP075 uses bounded `find` and `cat` operations. There is no `sh`, `bash`, command string, shell
parser, eval, subprocess selected by the model, package installation or arbitrary executable.
Every selected file read from the container must match the corresponding canonical snapshot
SHA-256 before its content may be returned to the model.

## Runtime binding and evidence

The Agent Runtime binding includes the immutable Sandbox policy, provider contract, foundation,
Product implementation identity and exact Agent/Tool graph. A post-preflight mutation invalidates
the prior confirmation.

Raw Tool arguments, raw Tool results, source content, host paths, image values and credentials are
not persisted. Bounded `tool.completed` evidence contains only workspace mode/materialization,
snapshot and image-binding hashes, file/count bounds, Docker call count, selected-file hash
verification, cleanup state, orphan count, and the disabled network/Shell/Apply-Patch flags.

Cleanup executes in `finally`. Deletion failure or a nonzero label-scoped orphan count fails the
Tool.

## Explicitly forbidden in STEP075

- SDK `SandboxAgent` defaults or SDK Docker client;
- general Agent-selected Sandbox capability;
- writable workspace, patch export or host source mutation;
- Shell, process execution, compilers, tests or dependency installation;
- network egress, exposed ports or service discovery;
- host bind, remote, FUSE or Docker socket mounts;
- API keys, Product environment or other secrets inside the container;
- Product Skill scripts/references/assets materialization;
- retained containers, snapshot/resume, automatic retry or warm pools;
- remote providers, distributed workers or user/model-selected provider/image/path.

## Next-step gate

STEP076 remains unselected until STEP075 deterministic and Windows live acceptance are recorded and
a fresh packaged code/Reference audit is completed.
