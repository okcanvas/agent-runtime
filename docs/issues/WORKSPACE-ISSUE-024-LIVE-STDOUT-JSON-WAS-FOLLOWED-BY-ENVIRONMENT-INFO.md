# WORKSPACE-ISSUE-024 — Live stdout JSON was followed by environment info

The Windows entrypoint printed the environment provenance notice to stdout after the child process emitted its JSON payload. Redirected Live output therefore contained a valid JSON object followed by an `[INFO]` line and was not parseable as one JSON document.

STEP004R2 sends the provenance notice to stderr. stdout remains the acceptance JSON only; the environment source name and loaded key names remain inside the secret-safe JSON evidence.
