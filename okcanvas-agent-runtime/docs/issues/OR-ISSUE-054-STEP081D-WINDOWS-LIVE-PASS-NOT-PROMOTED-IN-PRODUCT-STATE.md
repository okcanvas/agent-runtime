# OR-ISSUE-054 — STEP081D Windows live pass was not promoted in Product state

## Symptom

The real Windows `sh_run_step081d_live_acceptance` result passed 80/80, but the immutable STEP081D Product ZIP still reported the Windows gate as pending in `README.md`, `HANDOFF.md`, `PLANS.md`, and `RuntimeInfo`.

## Code-confirmed root cause

STEP081D packaged pending-state literals before the external Windows run existed. No later promotion STEP rewrote the Product state SOT after the user supplied the successful evidence.

## Impact

- Service capabilities exposed a stale `next_selected_step`.
- Architecture/capability Windows-live flags remained false.
- Documentation prohibited promotion even though the exact live contract had passed.

## Correction

STEP082B imports a compact, non-secret Windows evidence summary and normalizes the runtime/document state while preserving the immutable STEP081D parent ZIP.

## Recurrence gate

- `tests/test_step082b_coding_execution_plane_and_distribution_boundary.py`
- `scripts/run_step082b_acceptance.py`
- exact STEP081D live summary: 80/80, Architecture 40/40, model calls 2, Tool calls 1, cleanup completed, orphan count 0.
