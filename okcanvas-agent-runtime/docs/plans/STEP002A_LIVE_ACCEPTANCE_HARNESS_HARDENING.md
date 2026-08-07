# STEP002A_LIVE_ACCEPTANCE_HARNESS_HARDENING

## Objective
Make the existing STEP002 live-acceptance path repeatable and practical on the user's Windows environment without adding workspace write, MCP, API, UI, or new Agent behavior.

## Current code evidence

- STEP002 implementation is deterministic-test accepted but not live accepted.
- `scripts/run_step002_live_acceptance.py` used one persistent `docs/evidence/step002-live/thread.json` while each invocation created a different temporary workspace. A second acceptance invocation could therefore load a stale thread bound to a deleted workspace and fail before the first run.
- `src/okcanvas_agent_runtime/__init__.py` still reported `0.1.0` while `pyproject.toml` and `RuntimeInfo` reported `0.2.0`.
- No Windows launcher existed for setup, readiness, or live acceptance.

## In scope

- one executable baseline constant for version and current STEP;
- version consistency regression test against `pyproject.toml`;
- unique acceptance directory per invocation;
- thread and evidence files scoped to one acceptance invocation;
- refusal to overwrite an existing acceptance directory;
- acceptance summary written on pass or failure after a run directory exists;
- first/second run hashes, versions, thread information, and checks in the summary;
- exclusion of local live-acceptance evidence from source packaging;
- Windows setup, doctor, and STEP002 live-acceptance launchers;
- local `.env.local.cmd` pattern ignored by Git.

## Explicit non-scope

- accepting STEP002 without a live model/Codex run;
- workspace write;
- MCP;
- Session or RunState persistence;
- REST/SSE/UI;
- automatic Codex CLI installation;
- Windows command execution in the Linux packaging environment.

## Acceptance criteria

- all pre-existing tests remain green;
- stale root thread evidence cannot affect a new acceptance invocation;
- two fake accepted runs preserve one thread and mark the second as resumed;
- an existing acceptance directory is never overwritten;
- missing model credentials create no acceptance directory;
- runtime, package, and `RuntimeInfo` versions match;
- reference trees remain unchanged;
- final source ZIP re-extracts and passes the same deterministic checks.

## Exact next action

On Windows:

```bat
sh_setup.cmd
copy .env.local.cmd.example .env.local.cmd
rem edit local values
sh_doctor.cmd
sh_run_step002_live_acceptance.cmd
```

A real successful run is still required before STEP002 is marked live accepted.
