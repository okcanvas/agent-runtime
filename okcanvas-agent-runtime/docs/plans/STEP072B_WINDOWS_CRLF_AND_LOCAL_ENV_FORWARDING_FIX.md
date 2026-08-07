# STEP072B — Windows CRLF and local environment forwarding fix

- version: `2.52.2`
- predecessor: STEP072A / 2.52.1
- state: `WINDOWS_LIVE_ACCEPTED`

## Confirmed Windows triggers

The real Windows STEP072A run produced two independent failures.

```text
Deterministic acceptance: FAILED 23/24
Focused tests: 44 passed, 1 failed
Failure: collision fixture observed 19 bytes while comparing with an 18-byte LF payload

Live acceptance: FAILED 5/15
Bytecode isolation present/active/outside project: true
Readiness: OPENAI_API_KEY_MISSING, OKCANVAS_AGENT_MODEL_MISSING
```

The first failure is a test portability defect: `Path.write_text()` translated LF to CRLF on
Windows. The fixture must write exact UTF-8 bytes when it asserts byte size.

The second failure is a launcher composition defect: the STEP072A live launcher started the live
script directly through the bytecode-isolation wrapper and therefore bypassed `windows_entrypoint.py`,
the data-only `.env.local` loader.

Compact evidence is recorded in `docs/evidence/STEP072A_WINDOWS_ACCEPTANCE_SUMMARY.json`.

## Objective

Preserve the temporary `PYTHONPYCACHEPREFIX` isolation while restoring the canonical local environment
loading path for live acceptance. Keep the test fixture byte-exact on Windows and Unix.

## Contract

Deterministic collision fixtures use `Path.write_bytes()` with explicit UTF-8 bytes.

Current live execution starts through:

```text
python_bytecode_isolation.py
  -> windows_entrypoint.py
       -> data-only .env.local parsing
       -> run_step072b_live_acceptance.py
            -> retained STEP072A governed live workflow
```

The API Key remains environment-only, never appears on the command line and is redacted from compact
output. The temporary pycache prefix is inherited across all child processes.

## Scope

- correct the stale-bytecode collision fixture for Windows CRLF behavior;
- route STEP072A and STEP072B live launchers through the data-only local environment loader;
- prove API Key, model and `PYTHONPYCACHEPREFIX` reach the current child interpreter;
- preserve STEP072 trace-export policy and `document-review-v1` identities;
- add STEP072B deterministic and live acceptance;
- package the Windows STEP072A failure summary without secrets or raw attachments.

## Non-scope

- changing `.env.local` syntax or executing it as a command file;
- changing the model, Skill, trace policy, attachment or governed Submission contracts;
- changing Python bytecode validation rules;
- selecting STEP073.

## Windows acceptance

```cmd
sh_setup.cmd
sh_run_step072b_acceptance.cmd
sh_run_step072b_live_acceptance.cmd
```

The deterministic command must pass the exact-byte collision test and all retained historical tests.
The live command must show an active pycache prefix outside the project, a ready local environment,
one successful `gpt-4.1` model call, no trace-export diagnostic and no persisted API Key/raw PDF.

## Windows closure

The corrected package passed the reported real Windows commands:

```text
Deterministic acceptance: 24/24 PASS
Focused tests: 51/51 PASS
Historical tests: 41/41 PASS
Live acceptance: 17/17 PASS
Model: gpt-4.1
Model calls: 1
Usage: 827 input / 420 output / 1,247 total tokens
Terminal status: SUCCEEDED
Pycache prefix active and outside project: true
Local environment forwarded: true
Trace error markers: []
API Key/raw attachment persisted: false/false
Workspace cleanup completed: true
```

Compact evidence is `docs/evidence/STEP072B_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`. The reusable
incident analysis and launcher review rules are
`docs/38-WINDOWS-PYTHON-LAUNCHER-PORTABILITY.md`.

