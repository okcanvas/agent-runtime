# STEP079A — Windows entrypoint command registration fix

## Binding identity

```text
STEP079A_WINDOWS_ENTRYPOINT_COMMAND_REGISTRATION_FIX
version: 2.59.1
```

## Selected problem

The STEP079 Windows live launcher is packaging-complete but not executable because its command exists only in the dispatch branch and not in the argparse choice registry.

## Scope

1. Register the exact existing command in `_parser()`.
2. Route it to the corrective STEP079A live acceptance script.
3. Preserve `sh_run_step079_live_acceptance.cmd` as a compatibility launcher.
4. Add executable parser, dispatch, environment-forwarding, and launcher-alignment tests.
5. Record the exact Windows failure and update the ZIP-only handoff.
6. Re-run deterministic, focused, historical, full Python, Node, Reference, npm-pack, and fresh-ZIP gates.

## Non-goals

- No Task/Run ownership algorithm change.
- No Sandbox, Docker, model, Tool, archive, or persistence boundary change.
- No selection of STEP080.
- No claim that STEP079/STEP079A is Windows-live accepted before a corrected Windows rerun.

## Acceptance

Deterministic acceptance must prove the parser accepts the command and the dispatcher invokes `run_step079a_live_acceptance.py` with both compatibility and corrective opt-in flags. Windows live acceptance must execute the existing immutable project workflow and return the STEP079A schema with the exact expected check total.
