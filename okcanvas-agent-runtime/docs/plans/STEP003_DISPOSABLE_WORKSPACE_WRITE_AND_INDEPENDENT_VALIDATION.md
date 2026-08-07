# STEP003 — Disposable Workspace Write and Independent Validation

## Objective

Prove a controlled code-repair vertical slice without granting Codex access to the source fixture or
an external project. Codex may mutate one exact file in a temporary Git copy; an independent pytest
validator outside Codex is the sole authority for test success.

## Current code evidence

STEP002C live acceptance proved read-only file discovery, Codex event evidence, thread resume, and
source-tree immutability on Windows. It also showed that pytest was unavailable inside the Codex
subprocess, so test authority must be separated from model/tool claims.

## In scope

- official experimental `codex_tool` with `sandbox_mode=workspace-write`;
- one explicitly approved disposable Git copy;
- exact existing-file allowlist and expected-file contract;
- no untracked, staged, deleted, renamed, binary, committed, web-search, or MCP changes;
- Git patch and SHA-256 evidence;
- post-run Agent and Codex token budgets;
- deterministic pytest validator invoked with `sys.executable`, not by Codex;
- acceptance fixture with one known failing test;
- Windows live-acceptance launcher.

## Non-scope

- external or user project mutation;
- automatic promotion of the patch;
- arbitrary validator commands;
- package installation by Codex;
- command-level Codex HITL;
- MCP, API/SSE/UI, PlanVM, task queue, or Windows worker;
- Java, Vue, PostgreSQL, browser, or PDF validation.

## Acceptance criteria

1. Baseline independent validation observes exactly one failing fixture test.
2. Codex write run succeeds with all four explicit opt-ins.
3. Only `src/inventory/pricing.py` changes.
4. HEAD is unchanged, patch evidence exists, and no staged/untracked/binary/deleted files exist.
5. Independent post-validation observes at least one passing test and no failures/errors.
6. The source fixture tree hash is unchanged.
7. Agent and Codex token usage remain below the configured post-run budgets.
8. All local unit/integration tests and reference integrity checks pass.

## Failure and recovery

Any boundary failure returns a typed failed envelope and does not emit an accepted patch. The
temporary workspace is discarded by the acceptance harness. The source fixture is never promoted or
modified. A token-budget failure rejects the result even though the already-incurred usage remains
recorded.

## Current status

Implemented and deterministically tested. Live Codex workspace-write acceptance has not yet been
executed and must not be claimed until `sh_run_step003_live_acceptance.cmd` returns a PASSED summary.
