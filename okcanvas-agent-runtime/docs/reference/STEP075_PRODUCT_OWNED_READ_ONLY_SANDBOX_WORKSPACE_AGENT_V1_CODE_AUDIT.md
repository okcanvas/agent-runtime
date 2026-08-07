# STEP075 Product-owned Read-only Sandbox Workspace Agent V1 — Code Audit

## Audited baseline

- predecessor ZIP: STEP074 version 2.54.0;
- predecessor deterministic Windows result: 28/28 PASS;
- predecessor Docker live result: 27/27 PASS;
- selected STEP: `STEP075_PRODUCT_OWNED_READ_ONLY_SANDBOX_WORKSPACE_AGENT_V1`;
- current version: 2.55.0.

## Findings from the fresh audit

1. The existing `InvocationWorkspacePlanner` only calculated host paths; it did not provide a
   hardened physical Sandbox workspace.
2. The retained SDK `SandboxAgent` default capability set includes Filesystem/Shell/Compaction, and
   Filesystem includes Apply Patch. Product code must not instantiate these defaults.
3. Host bind mounts would expose mutable host content and weaken cleanup. STEP075 therefore uses a
   bounded snapshot copied into a container-owned tmpfs.
4. The STEP074 lifecycle used an image default command only. STEP075 needs a long-lived container,
   but the command is still Product-fixed (`tail -f /dev/null`), not user/model selected.
5. Direct container reads must be hash-checked against the immutable snapshot; host-side ranking
   alone is not sufficient evidence that the container saw the same bytes.
6. Accepted CP949/UTF-8-SIG text must be normalized to UTF-8 before hashing because Docker CLI text
   output is decoded as UTF-8.
7. Raw Tool results are forbidden in Events. A separate strict Sandbox Tool output contract supplies
   only bounded lifecycle and identity evidence.

## Implemented Product boundary

- one exact Agent and one exact read-only Tool;
- 26 predecessor Agents remain `workspace_access=none`;
- policy modes active only `none` and `sandbox-readonly-v1`;
- snapshot limits: 3,000 files, 32 MiB total, 512 KiB/file;
- excluded source families include VCS, virtual environments, build output, dependency trees,
  caches, `.local`, and `/reference`;
- Docker: immutable local RepoDigest, `--pull=never`, network none, no ports/binds/secrets, read-only
  rootfs, cap-drop ALL, no-new-privileges, non-root 65532:65532, bounded memory/CPU/PIDs;
- workspace: root-owned tmpfs `/workspace`, 32 MiB, noexec/nosuid/nodev;
- fixed command allowlist only; no Shell parser;
- selected file hashes verified; forced deletion and orphan-zero required;
- Runtime binding includes policy/provider/foundation/Product implementation and the exact Agent/Tool
  graph.

## Security conclusions

- No SDK SandboxAgent, SDK Docker client or SDK default capabilities are used.
- No host filesystem path is exposed through service metadata.
- No API key or Product environment is injected into the container.
- The model cannot choose a provider, image, host path, command, filename outside bounded evidence,
  network destination, mount or capability.
- The output Event contains hashes/status only, not source text or raw Tool output.

## Validation status

- STEP075 deterministic acceptance: 28/28 PASS.
- Focused STEP075/Sandbox/provider tests: 89/89 PASS.
- Historical Skill/trace/service tests: 47/47 PASS.
- Full Python regression: 799/799 PASS across 206 test files.
- Python compileall, committed TypeScript integrity, Node 14/14, Reference 4/4 and npm pack 23 files pass.
- Deterministic Docker/network/model calls remain 0/0/0.
- Windows live execution remains pending until user-reported output is received.
- Candidate ZIP `2ac44a0b265762e7849762845a5882a8fd8e65102dc91e4b893ca31d0d806c13` independently passed STEP075 28/28 and full Python 799/799 with canonical root 1, 3035 entries and 0 forbidden files.
