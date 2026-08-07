# STEP003C — Disposable workspace write live acceptance

## Objective

Promote the controlled disposable workspace-write slice to a live-accepted baseline using retained Windows execution evidence.

## Accepted facts

- Codex changed exactly `src/inventory/pricing.py` in a disposable Git copy.
- The patch contained one addition and one deletion.
- Baseline independent validation observed the expected single failure.
- Post-patch independent validation passed the test.
- Original fixture tree and Git HEAD remained unchanged.
- No untracked, staged, committed, renamed, deleted, binary, Web Search, or MCP changes were accepted.
- Cleanup completed on the first attempt after bytecode suppression.
- All ten acceptance checks passed.

## Explicit boundary

This acceptance proves controlled fixture writing only. It does not enable arbitrary external-project writing, arbitrary shell, MCP, automatic patch promotion, or production changes.

## Result

Accepted. `workspace_write_live_accepted=true`; `workspace_write_enabled=false` remains the default product boundary.

## Next step

STEP004 will prove whole-run approval, serialized `RunState`, process termination, approval/rejection, and resume. It must reuse the controlled fixture and must not add API/SSE/UI or external repositories.
