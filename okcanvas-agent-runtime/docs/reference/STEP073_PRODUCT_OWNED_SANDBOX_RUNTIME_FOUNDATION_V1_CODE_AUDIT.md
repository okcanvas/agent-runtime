# STEP073 Product-owned Sandbox Runtime Foundation V1 — Code Audit

## Audited baseline

The implementation was derived from the packaged STEP072B post-live ZIP SHA-256
`6bf3457f9e31a205c36f6162ed6d2652f0fefb8e2fa137dd7d99a9f79cd53bfd`. The audit read the Product
Runtime binding, Agent definition catalog, invocation workspace planner, service-client boundary,
Skill catalog and retained SDK Sandbox source before selecting STEP073.

## Existing Product boundary

All current Agent definitions are rejected unless `workspace_access=none`. The
`InvocationWorkspacePlanner` only derives a server-controlled path and explicitly does not create or
grant filesystem access. No Sandbox provider registry, session lifecycle, Docker lifecycle, quota,
network policy, physical workspace materialization or Sandbox Artifact export existed.

## Retained SDK facts

The following retained 0.19.0 source identities were audited without importing executable Reference
code:

```text
capabilities/capabilities.py  7a40308ac95dd8f649bc06047af0d7183b76338120ec6453acef9991f9d1d406
capabilities/filesystem.py    9810f7878518c708c16a2b55a2748b84eabeb0c106e7d223d6b52088c1bbf3f3
capabilities/shell.py         0ddacb568dde2fe06eaea61f8ffe97f5556d0f3aea73693996888bc87331cfbf
sandbox_agent.py              8e90f64f1c5a3e9ae062c490300c9f6d1fa49958873c0c05a440c184b8ee18be
sandboxes/docker.py           8f1cc63295eee21b2a78b85f17082586c7be6e4ac4f4504d187e0eb672d2eb35
```

Observed source behavior:

- default capabilities are `Filesystem(), Shell(), Compaction()`;
- Filesystem exposes `SandboxApplyPatchTool` and `ViewImageTool`;
- Shell exposes `ExecCommandTool` and optional stdin interaction;
- `SandboxAgent.capabilities` uses the default capability factory when omitted;
- `DockerSandboxClientOptions` contains image and exposed ports;
- `_create_container` pulls a missing image;
- some manifest mount modes add `/dev/fuse`, `SYS_ADMIN`, and `apparmor:unconfined`;
- Docker execution hardening required by the Product is not a closed input contract in that client.

This proves that SDK defaults cannot be the Product authority. It does not claim the SDK is defective;
it establishes the stricter OKCanvas boundary.

## Implemented Product contract

`SandboxRuntimeCatalog` loads two immutable JSON contracts, rejects unsafe/symbolic paths, exact-key
mismatch and forbidden capability mutation, computes canonical policy/provider/foundation hashes, and
permits only active workspace access `none`.

`SandboxRuntimeService` exposes public metadata and raises
`SandboxExecutionDisabledError` on execution. Product source does not import `agents.sandbox`, create
`DockerSandboxClient`, call Docker, materialize a workspace, or execute a model.

`AgentRuntimeBindingCatalog` includes the complete Sandbox foundation and the combined Product
Sandbox implementation SHA in every Agent binding and execution-engine fingerprint. Therefore a
change requires fresh preflight and confirmation.

The service endpoint `/v1/service/sandbox-runtime` is authenticated and metadata-only. It returns no
image value, host path, Docker connection, secret, executable code, mutable config or workspace data.

## Deferred provider enforcement

The provider contract records controls required by the next physical lifecycle step, including
immutable image digest selection, no runtime pull, network none, no ports/mounts/socket, non-root,
cap-drop ALL, no-new-privileges, read-only root, deletion and orphan reconciliation. STEP073 does not
claim those controls were exercised because no container is created.

## Audit conclusion

STEP073 is correctly limited to a disabled, immutable, confirmation-bound Sandbox foundation. A
physical Docker lifecycle must be a separate audited step and must not instantiate the retained SDK
Docker client as the Product policy implementation without a hardened adapter.

## Deterministic verification

The source tree passed STEP073 acceptance 26/26, focused tests 40/40, historical Skill/trace/service
regression 47/47, full Python regression 781/781 across 204 test files, Node 14/14, npm pack dry-run
23 files and Reference integrity 4/4. Docker calls, provider network calls and model calls were all zero.
A candidate ZIP with canonical root 1, 3,005 entries and zero forbidden files was independently
extracted and repeated STEP073 26/26, Python 781/781, Node 14/14, Reference 4/4 and npm pack 23 files.
Windows acceptance remains unexecuted for this package.
