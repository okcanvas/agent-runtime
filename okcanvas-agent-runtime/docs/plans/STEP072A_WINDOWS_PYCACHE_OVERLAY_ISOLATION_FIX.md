# STEP072A — Windows pycache overlay isolation fix

- version: `2.52.1`
- predecessor: STEP072 / 2.52.0
- state: `IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_RERUN_PENDING`

## Confirmed trigger

The real Windows STEP072 run produced two different outcomes:

```text
sh_run_step072_acceptance: 28/29 FAILED
sh_run_step072_live_acceptance: 13/13 PASSED
```

The single deterministic failure came from `/v1/service/capabilities` returning the old STEP071
`next_selected_step`, while the STEP072 source, service policy and direct RuntimeInfo checks all
contained the STEP072 value.

The STEP071 and STEP072 ZIP entries for
`src/okcanvas_agent_runtime/service_clients/routes.py` have the same deterministic ZIP timestamp and
exactly the same 32,523-byte size. Only the `STEP071`/`STEP072` text changed. Python timestamp-based
bytecode validation can therefore accept an existing STEP071 `.pyc` after an in-place source overlay.
The new regression fixture reproduces this exact same-timestamp and same-size stale import and proves
that an isolated `PYTHONPYCACHEPREFIX` imports the current source.

## Objective

Make current Windows launchers independent of adjacent bytecode left by an older extracted source
baseline. Do not weaken source determinism, Runtime policy, Skill identity or the successful STEP072
trace-export behavior.

## Contract

Current Windows launchers start through:

```text
scripts/python_bytecode_isolation.py
```

The wrapper:

1. creates a process-owned temporary directory;
2. passes it as `PYTHONPYCACHEPREFIX` before the child interpreter starts;
3. invokes the exact project Python script without a shell;
4. lets descendants reuse the same prefix;
5. deletes the temporary prefix after the child exits.

Adjacent `__pycache__` and `.pyc` files are therefore never consulted by the launched Product or
Acceptance process.

## Scope

- protect the current API launcher;
- protect STEP072 and STEP072A deterministic/live launchers;
- record the exact STEP072 Windows deterministic failure and live success;
- mark STEP072 trace-export behavior as Windows-live accepted;
- add a deterministic stale-bytecode reproduction test;
- preserve the immutable trace-export policy and `document-review-v1` identities.

## Non-scope

- changing Python or ZIP deterministic timestamp rules;
- deleting user directories globally;
- accepting source overlays as a packaging requirement;
- changing OpenAI model, trace, Skill, attachment or service-client contracts;
- selecting STEP073.

## Windows acceptance

Run from the corrected ZIP:

```cmd
sh_setup.cmd
sh_run_step072a_acceptance.cmd
sh_run_step072a_live_acceptance.cmd
```

The deterministic command must pass all checks, including the historical service metadata test. The
live command must show an active temporary pycache prefix outside the project, one successful
`gpt-4.1` call, no trace-export diagnostic, no persisted API Key/raw PDF and completed cleanup.
