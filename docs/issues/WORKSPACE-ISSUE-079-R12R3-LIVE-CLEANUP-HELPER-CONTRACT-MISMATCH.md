# WORKSPACE-ISSUE-079 — R12R3 Live Cleanup Helper Contract Mismatch

Status: FIXED_IN_R12R4_LIVE_HARNESS

R12R3 called `remove_temp_tree(temp, retry_error_types=...)`, but the shared helper accepts only the path and returns `(removed, error_types)`. This produced a cleanup `TypeError` unrelated to Product behavior.

R12R4 destructures the exact helper result and records `TemporaryTreeRemovalFailed` only when removal itself fails. Future harness revisions must call shared cleanup helpers using their exact source contract rather than inferred keyword parameters.
