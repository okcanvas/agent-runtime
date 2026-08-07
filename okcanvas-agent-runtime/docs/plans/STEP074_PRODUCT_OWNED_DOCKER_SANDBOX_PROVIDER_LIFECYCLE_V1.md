# STEP074_PRODUCT_OWNED_DOCKER_SANDBOX_PROVIDER_LIFECYCLE_V1

## State

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_DOCKER_RERUN_PENDING`

## Objective

Turn the STEP073 contract-only `docker-local-v1` provider into one bounded Product-owned local-Docker
lifecycle without enabling an Agent workspace, model execution, Shell, patching, network, mounts,
ports, secrets, resume, snapshots, Skill materialization, or SDK Sandbox defaults.

## Accepted predecessor

STEP073 Windows deterministic acceptance passed 26/26 with 26 Agent definitions, all
`workspace_access=none`, Docker/network/model calls zero, focused 38 passed plus two unavailable
Windows symlink cases, historical 47/47, and Node 14/14.

## Product lifecycle

```text
operator-selected local image tag or exact digest
  -> docker image inspect only
  -> resolve one local RepoDigest
  -> docker container create --pull=never with hardened flags
  -> inspect and independently verify effective security settings
  -> start the image default command only
  -> require exited/0
  -> delete container and anonymous volumes
  -> label-filtered orphan check
```

No Product API accepts an image value. The image selector exists only in the Windows live acceptance
environment as `OKCANVAS_SANDBOX_LIVE_IMAGE`; the provider resolves it to a local immutable
RepoDigest before creation. Missing images fail readiness. Runtime pull is forbidden.

## Hardened create contract

- `--pull=never`
- `--network none`
- no published ports
- no mounts or Docker socket
- `--read-only`
- `--cap-drop ALL`
- no `--cap-add`
- `--security-opt no-new-privileges`
- `--user 65532:65532`
- memory 128 MiB
- CPU 0.5
- PID limit 64
- restart policy `no`
- bounded command timeout and output
- exact Product labels
- image default command only
- no container environment injection

## Runtime binding

The policy/provider JSON, lifecycle implementation module, foundation SHA and Product Sandbox Runtime
SHA remain confirmation-bound for every Agent even though all current Agents remain workspace-free.

## Acceptance

Deterministic acceptance uses a scripted Docker runner and issues zero real Docker/network/model
calls. Windows live acceptance requires Docker Desktop/Engine and one already-local image with a
RepoDigest. `hello-world:latest` is the default discovery tag; the acceptance never pulls it.

## Deferred

Agent workspace materialization, read-only filesystem tools, SDK `SandboxAgent`, patch export, Shell,
network, dependency installation, session resume, remote providers and Skill materialization remain
disabled and require later audited STEPs.


## Deterministic validation

```text
STEP074 Acceptance                    28/28 PASS
Focused STEP074/provider tests        71/71 PASS
Historical Skill/trace/service        47/47 PASS
Full Python regression               785/785 PASS across 205 files
Node tests                             14/14 PASS
Reference integrity                     4/4 PASS
npm pack dry-run                      23 files PASS
real Docker/network/model calls           0/0/0
```

Windows Docker live acceptance remains pending and is the only remaining STEP074 execution gate.


## Candidate fresh extraction

Candidate ZIP SHA-256 `8a3479d802300a4cc063720224ef2ccb01e4ca898a7d360ef580d106b3609a21`
was extracted into a new directory and passed STEP074 28/28, full Python 785/785, Node 14/14,
Reference 4/4 and npm pack dry-run 23 files. It had one canonical root, 3,016 entries and zero
forbidden files. The final distribution is repackaged after recording this evidence and revalidated.
