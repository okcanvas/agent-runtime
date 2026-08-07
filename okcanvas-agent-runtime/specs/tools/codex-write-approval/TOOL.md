# `codex_workspace_write` approval Tool

This Function Tool wraps the complete STEP003 disposable write flow and always requires SDK approval.
The Tool accepts only an opaque execution ID. Execution data is restored from persisted RunState context.
The OpenAI API key is never placed in serialized context or approval metadata.
