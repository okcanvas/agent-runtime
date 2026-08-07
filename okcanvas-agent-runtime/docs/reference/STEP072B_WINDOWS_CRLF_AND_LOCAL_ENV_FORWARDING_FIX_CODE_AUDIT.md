# STEP072B code audit

## Audited evidence

The user-reported STEP072A deterministic failure was not a Product runtime failure. The failing test
used `Path.write_text()` and then compared the Windows filesystem size with the pre-translation LF
byte length. Windows wrote CRLF, producing 19 bytes instead of 18.

The live failure occurred before any provider call. The pycache prefix checks all passed, but
`OPENAI_API_KEY` and `OKCANVAS_AGENT_MODEL` were missing because
`sh_run_step072a_live_acceptance.cmd` bypassed `scripts/windows_entrypoint.py`.

## Code correction

`tests/test_step072a_windows_pycache_overlay_isolation_fix.py` now writes both old and new fixture
sources with `write_bytes(source.encode("utf-8"))`. The timestamp and size collision remains exact and
cross-platform.

`sh_run_step072a_live_acceptance.cmd` and `sh_run_step072b_live_acceptance.cmd` now start through:

```text
scripts/python_bytecode_isolation.py scripts/windows_entrypoint.py <live-command>
```

`windows_entrypoint.py` owns the only local environment loading path. It parses `.env.local` as data,
validates the allowlist, merges values into a child-only environment and never places the API Key on
the command line. The inherited `PYTHONPYCACHEPREFIX` remains in that environment.

## Regression coverage

`tests/test_step072b_windows_crlf_and_local_env_forwarding_fix.py` verifies:

- current version, STEP and pending Windows gate;
- exact STEP072A Windows failure evidence;
- exact-byte collision fixture writes;
- API Key/model/pycache forwarding through the data-only entrypoint;
- launcher composition for STEP072A and STEP072B;
- local-only live evidence and package exclusions.

## Preserved identities

```text
Trace policy SHA-256:
6567645dc74b2850bad374f4e73eab50958c6e3e63440b0361dcadcea0b249cc

Skill package SHA-256:
60fbfca861141837d4486499687fde4257b83bcb68362b6b0a0b6f40b8df07b5
```

Provider trace export remains disabled. Product-local trace IDs, Events, Artifacts and usage remain
enabled. No Tool, MCP, Hosted Tool, Shell or Network capability was added.

## Final Windows verification

The corrected STEP072B package passed deterministic 24/24 and live 17/17 on Windows. The live child
observed `gpt-4.1`, one model call, 1,247 total tokens, an active pycache prefix outside the project,
and the forwarded local environment. No provider trace diagnostic was emitted. The API Key and raw
attachment were not persisted, and workspace cleanup completed.

No launcher implementation changed during post-live closure. Runtime/service metadata now records the
accepted Windows state and gates the next selection on a fresh packaged-code audit. The recurring
design rules are elevated into `docs/38-WINDOWS-PYTHON-LAUNCHER-PORTABILITY.md` and linked from
`AGENTS.md`.

## Post-live package audit

The documentation closure did not change launcher execution logic, Skill identity, trace policy, or
Runtime binding. It changed only accepted-state metadata, the service-client next-selection gate,
compact Windows evidence, and binding documentation/tests. The candidate archive
`a4dfb9318496821db896a924fdffdee350348e8e717aef4316fd2c76b8df067c` had one canonical root, 2,989 entries, zero forbidden files, STEP072B Acceptance
26/26, full Python regression 757/757, Reference 4/4, direct Reference imports 0, and npm pack 23
files after fresh extraction.

