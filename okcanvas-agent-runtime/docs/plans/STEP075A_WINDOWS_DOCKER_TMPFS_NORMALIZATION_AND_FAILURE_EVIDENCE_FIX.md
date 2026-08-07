# STEP075A_WINDOWS_DOCKER_TMPFS_NORMALIZATION_AND_FAILURE_EVIDENCE_FIX

```text
version: 2.55.1
state: IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING
predecessor: STEP075_PRODUCT_OWNED_READ_ONLY_SANDBOX_WORKSPACE_AGENT_V1
```

## Trigger

STEP075 deterministic Windows acceptance passed 28/28. The real live run failed after the first model turn and `tool.started`, before `tool.completed`. The workspace was preserved, but the summary did not retain the exact Sandbox error code. A source audit also found an exact string comparison for Docker tmpfs options that is not portable across Docker normalization.

## Scope

- preserve the STEP075 Agent, Tool, Sandbox policy/provider, Runtime binding, image, workspace, and security contracts;
- replace exact tmpfs-string equality with fail-closed semantic validation;
- persist a bounded `tool.failed` Event with the stable Sandbox error code;
- add exact Windows failure evidence and an engineering Issue Registry;
- correct preserved-workspace database documentation to `databases/product.sqlite3`;
- rerun the same governed read-only Sandbox workflow.

## Explicit non-scope

- no Shell, Apply Patch, network, ports, mounts, secrets, image pull, resume, snapshot, Skill materialization, or new Agent/Tool;
- no relaxation of `rw,noexec,nosuid,nodev`, root ownership, mode 0755, 32 MiB tmpfs, non-root container execution, read-only rootfs, capability drop, resource limits, cleanup, or orphan-zero requirements;
- no STEP076 selection.

## Acceptance

Deterministic acceptance must prove:

1. exact 2.55.1/STEP075A baseline and gate;
2. STEP075 Windows failure summary and issue documents exist;
3. tmpfs order, size notation, and mode notation are normalized semantically;
4. missing `noexec`, relaxed mode, malformed or unknown options remain rejected;
5. bounded `tool.failed` evidence contains a stable code but no arguments/result/raw text;
6. STEP075 Agent/Tool/Runtime binding and all prior security contracts remain unchanged;
7. focused, historical, full Python, Node, Reference, compile, and packaging tests pass;
8. deterministic Docker/network/model calls remain zero.

Windows live acceptance must rerun the governed STEP075 workflow and require success. If it fails, the summary must contain `failure_diagnostics.tool_failed[].code` and the preserved database path.
