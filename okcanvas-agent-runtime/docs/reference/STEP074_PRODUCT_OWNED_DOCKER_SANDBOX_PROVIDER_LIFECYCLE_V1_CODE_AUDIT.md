# STEP074 Code Audit

## Audited baseline

- STEP073 packaged ZIP SHA-256: `f8a14b03d32d8c7bd30f6dfa533213c9913ccd1fca0a939c23d45a2bc7b3446b`
- STEP073 Windows result: 26/26 PASS
- STEP074 version: `2.54.0`

## Code-derived findings

1. STEP073 contained policy/provider identity and binding only; `SandboxRuntimeService` rejected all
   execution and Product code imported no SDK Sandbox or Docker implementation.
2. The retained SDK Docker client is not used. STEP074 uses a Product-owned Docker CLI adapter with
   `subprocess.run([...], shell=False)`, a restricted CLI environment and bounded output.
3. Local image discovery uses `docker image inspect`. A tag must resolve to a local `RepoDigests`
   entry; actual container creation uses that immutable digest.
4. `docker container create` explicitly passes `--pull=never`; no `docker pull` code path exists.
5. The create argument array includes network none, read-only root, cap-drop ALL,
   no-new-privileges, non-root UID/GID, memory/CPU/PID limits, no restart and exact labels. It contains
   no env, mount, publish, privileged or cap-add argument.
6. Effective Docker inspect state is validated before start. A mismatch fails before execution and
   still enters deletion.
7. The container runs only its image-default command, must exit with code zero, is forcibly removed
   with anonymous volumes, and is followed by a label-scoped orphan query.
8. The Docker CLI child environment excludes OpenAI keys, Product encryption keys, model IDs and
   other Product configuration. No value is injected into the container.
9. All 26 Agents remain `workspace_access=none`; STEP074 does not construct an SDK `SandboxAgent`,
   filesystem capability, Shell, Apply Patch or model call.
10. `/v1/service/sandbox-runtime` exposes lifecycle policy and limits but no requested image,
    immutable image digest, host path, Docker endpoint, credential or workspace content.

## Windows live risk retained

Docker Desktop/Engine behavior, local image availability, actual inspect field values and cleanup can
only be accepted on Windows. The live launcher uses bytecode isolation followed by the data-only
`.env.local` loader. Missing local image is a readiness failure and never triggers a pull.


## Deterministic validation evidence

- STEP074 acceptance: 28/28 PASS.
- Focused STEP074/provider/runtime tests: 71/71 PASS.
- Historical Skill/trace/service tests: 47/47 PASS.
- Full Python regression: 785/785 PASS across 205 test files.
- Node: 14/14 PASS; Reference: 4/4 PASS; npm pack dry-run: 23 files.
- Real Docker, external network and model calls: 0/0/0.
- Windows Docker lifecycle remains unaccepted until `sh_run_step074_live_acceptance.cmd` passes.


## Candidate fresh extraction

Candidate ZIP SHA-256 `8a3479d802300a4cc063720224ef2ccb01e4ca898a7d360ef580d106b3609a21`
was extracted into a new directory and passed STEP074 28/28, full Python 785/785, Node 14/14,
Reference 4/4 and npm pack dry-run 23 files. It had one canonical root, 3,016 entries and zero
forbidden files. The final distribution is repackaged after recording this evidence and revalidated.
