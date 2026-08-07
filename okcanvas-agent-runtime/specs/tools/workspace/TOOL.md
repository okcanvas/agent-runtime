# Disposable Workspace Tool

STEP003 permits mutation only in a temporary Git copy created by the acceptance harness. The source
fixture and external projects are never passed to Codex write mode. A clean committed baseline,
exact file allowlist, unchanged HEAD, no symlinks, no untracked files, no staged changes, no binary
changes, and an external patch artifact are mandatory.
