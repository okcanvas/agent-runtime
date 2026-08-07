# STEP030A — Windows project-venv launcher fix

Status: **WINDOWS_LIVE_ACCEPTED**

## Finding

The packaged `sh_run_step030_acceptance.cmd` invoked bare `python`, unlike the established project-venv launchers. On Windows this selected an interpreter without FastAPI and stopped before acceptance setup.

## Scope

- pin the STEP030 launcher to `.venv\Scripts\python.exe`;
- fail closed with an explicit `sh_setup.cmd` instruction when `.venv` is absent;
- add a repository-wide launcher contract preventing bare Python regressions;
- preserve the existing STEP030 acceptance script and all Product contracts.

## Excluded

No dependency substitution, global Python installation, PATH mutation, environment-file execution, business logic change, source authority, Tool/MCP expansion, or write capability.

## Windows completion

Run `sh_setup.cmd` and then `sh_run_step030_acceptance.cmd`. The actual STEP030 15-check result must pass; successful static launcher inspection alone does not close STEP030.
