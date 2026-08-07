# WORKSPACE-ISSUE-039 — Duplicate local environment key blocked Live preflight

## State

```text
WINDOWS_LIVE_ACCEPTED_RECURRENCE_RECORDED
```

## Evidence

A current STEP008R4R6 Windows Live invocation failed before Product execution with:

```text
.env.local:8: duplicate environment variable OKCANVAS_CODEX_MODEL
```

Code inspection of `okcanvas-agent-runtime/scripts/windows_entrypoint.py` confirmed that
`parse_environment_text()` intentionally raises `LocalEnvironmentError` when a key is already
present in the same environment file. The failure was therefore a local configuration
preflight rejection, not an OpenAI, Runtime, Connector or PostgreSQL failure.

## Correction

The duplicate `OKCANVAS_CODEX_MODEL` declaration was removed from `.env.local`. The user then
reported that the current Windows deterministic and Windows Live OpenAI gates both passed.
The local environment file remains excluded from package identity and is not persisted.

## Recurrence gate

- Keep duplicate-key rejection fail-fast; do not silently use first/last value.
- Diagnose `.env.local:<line>: duplicate environment variable <KEY>` as configuration preflight.
- Before changing Product code, inspect the local environment file for duplicate keys.
- Never copy `.env.local` or its secret values into package evidence.
