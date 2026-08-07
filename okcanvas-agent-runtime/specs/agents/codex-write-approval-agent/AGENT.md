# Codex write approval Agent

Purpose: request exactly one whole-run approval before the already accepted disposable Codex write flow.

The Agent receives only an opaque execution ID. The actual code request, workspace, allowlist, and artifact paths are restored from persisted RunState context. It must not reinterpret or rewrite the code task.
