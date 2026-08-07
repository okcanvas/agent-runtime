# OR-ISSUE-095 — Bounded regression checkpoint ignored test-content drift

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_PENDING`

## Found in

`STEP086R1_GROUPWARE_SUBAGENT_AND_EXTERNAL_MCP_BOUNDARY_ALIGNMENT`

## Problem

The bounded Python regression checkpoint considered an existing result compatible when STEP,
version, test-file count, chunk size and timeout matched. It did not hash test file paths or contents.
After a test was corrected without changing the total file count, completed chunks from the earlier
source state could be reused.

## Risk

A later full-regression record could combine results produced from different source/test states and
therefore overstate final coverage.

## Correction

- Added `test_inventory_sha256` over every `tests/test_*.py` relative path and file-content SHA-256.
- Persisted the inventory hash in every checkpoint payload.
- Reject existing checkpoints when the inventory hash differs.
- Added a deterministic regression proving content changes alter the inventory hash.

## Recurrence gate

Final source and Fresh-ZIP Python regression records must contain a current test inventory SHA-256.
No checkpoint may be resumed solely because its test-file count matches.
