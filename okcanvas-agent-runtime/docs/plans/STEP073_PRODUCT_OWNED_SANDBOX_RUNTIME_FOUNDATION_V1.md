# STEP073 — Product-owned Sandbox Runtime Foundation V1

## Baseline

- predecessor: `STEP072B_WINDOWS_CRLF_AND_LOCAL_ENV_FORWARDING_FIX`
- predecessor state: `WINDOWS_LIVE_ACCEPTED`
- target version: `2.53.0`

## Goal

Establish a Product-owned immutable Sandbox policy and disabled local-Docker provider contract, bind
both identities into every Agent Runtime fingerprint, and expose authenticated metadata without
creating a physical workspace or container.

## Source audit decisions

The retained OpenAI Agents SDK 0.19.0 Sandbox implementation is useful as a future adapter surface,
but its defaults are not acceptable Product policy:

- `Capabilities.default()` returns Filesystem, Shell and Compaction;
- Filesystem includes Apply Patch;
- `SandboxAgent.capabilities` defaults to that set;
- the retained Docker client pulls a missing image;
- some mount modes add `SYS_ADMIN` and `apparmor:unconfined`;
- the basic Docker options expose image and ports but do not close the Product quota, secret,
  non-root, capability-drop and lifecycle contract.

STEP073 therefore implements no SDK Sandbox or Docker call.

## Scope

- strict policy JSON below `specs/sandbox/policies`;
- strict provider JSON below `specs/sandbox/providers/docker-local-v1`;
- Product-owned catalog, models, fail-closed service and hashes;
- Agent Runtime binding integration;
- authenticated `/v1/service/sandbox-runtime` metadata endpoint;
- Runtime/service capability flags;
- SDK source audit anchored to retained source hashes;
- deterministic and Windows acceptance launcher.

## Closed capability boundary

```text
execution                    false
physical workspace           false
active workspace mode        none
Docker calls                 false
network                      none
ports                        []
host bind mounts             false
remote mounts                false
Docker socket mount          false
secrets                      false
runtime image pull           false
resume/snapshot              false/false
Shell/Apply Patch            false/false
Skill materialization        false
model-selected provider/path false/false
SDK default capabilities     forbidden
```

## Explicitly deferred

- container create/start/stop/delete;
- image digest selection and preinstallation acceptance;
- CPU, memory, PID, execution-time and output quotas;
- non-root and read-only-root enforcement;
- Artifact materialization/export;
- cleanup and orphan reconciliation implementation;
- read-only filesystem tools;
- writable patch workspace;
- Shell and dependency execution;
- Sandbox Skills and lazy loading;
- remote providers, egress and warm pools.

## Acceptance

- exact policy/provider schemas and identities;
- unknown fields, symlinks and forbidden mutations fail closed;
- every Agent binding contains identical Sandbox foundation and implementation SHA;
- every current Agent remains `workspace_access=none`;
- no Product import or construction of SDK Sandbox/Docker objects;
- upstream default capability and Docker behavior audited by retained source hashes;
- service response is authenticated and metadata-only;
- Docker, network and model calls remain zero;
- focused, historical, full Python, Node, Reference and package checks pass;
- STEP074 remains unselected pending Windows result and fresh audit.

## Deterministic result

```text
STEP073 acceptance                  26/26 PASS
Focused STEP073/runtime tests       40/40 PASS
Historical Skill/trace/service      47/47 PASS
Full Python regression             781/781 PASS
Node tests                           14/14 PASS
npm pack dry-run                    23 files PASS
Reference integrity                   4/4 PASS
Docker/network/model calls           0/0/0
```

Windows rerun remains pending.
