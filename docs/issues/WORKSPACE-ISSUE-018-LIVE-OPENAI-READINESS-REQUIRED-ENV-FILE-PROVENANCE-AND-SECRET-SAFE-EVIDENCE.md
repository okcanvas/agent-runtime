# WORKSPACE-ISSUE-018 — Live OpenAI readiness lacked environment-file provenance and secret-safe evidence

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_PENDING`

## Observed boundary

The real Windows STEP003R2 run passed 27/27, but it deliberately used the deterministic OpenAI Agents boundary. The user confirmed that Windows already stores the OpenAI API key and selected model in the Runtime local environment file. Before STEP004 there was no Workspace-level Live command that proved:

- the official Runtime local environment loader supplied both values,
- the values were not inherited from an unrelated parent shell,
- the actual OpenAI model, Root Session, stateless child, Connector and Node Example were crossed in one run,
- key and bearer values remained absent from argv, stdout, exceptions and evidence.

## Correction

- `windows_entrypoint.py` exports only the loaded environment filename and loaded variable names to the child process.
- `sh_run_workspace_step004_live_acceptance.cmd` invokes the Runtime's official environment loader.
- `run_workspace_step004_live_acceptance.py` requires explicit opt-in, `.env.local` or `.env.local.cmd` provenance, and the exact names `OPENAI_API_KEY` and `OKCANVAS_AGENT_MODEL`.
- The key value is never fingerprinted or persisted.
- Provider failures are reduced to a safe category and exception type; raw provider errors are not retained.
- Local environment files and mutable Live evidence remain outside Workspace identity and ZIP packaging.

## Recurrence gates

- `tests/test_workspace_step004_live_readiness.py`
- STEP004 deterministic readiness acceptance
- STEP004 Windows Live acceptance
