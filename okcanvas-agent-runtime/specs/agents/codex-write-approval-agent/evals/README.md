# STEP004 acceptance

Two independent disposable workspaces are required.

- Approve: prepare must persist one interruption without mutation; a second process approves; Codex executes once; independent pytest passes; replay is blocked.
- Reject: prepare must persist one interruption without mutation; a second process rejects; Codex execution count remains zero; workspace remains unchanged; replay is blocked.
