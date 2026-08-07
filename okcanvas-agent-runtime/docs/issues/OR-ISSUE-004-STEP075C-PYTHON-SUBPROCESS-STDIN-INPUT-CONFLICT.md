# OR-ISSUE-004 — STEP075C Python subprocess stdin/input conflict

## Status

`WINDOWS_FIX_ACCEPTED_DISTINCT_HASH_DOMAIN_FAILURE_REMAINS`

## Exact symptom

STEP075C Windows live acceptance entered `sandbox_project_readonly_inspect` after one `gpt-4.1` model turn. Events then contained `tool.started`, followed directly by `agent.failed` and `run.failed`; no `tool.failed` Event and no Docker operation evidence were produced. The run passed 13/29 checks and preserved its acceptance workspace.

## Code-confirmed root cause

`SubprocessDockerCommandRunner._run()` passed both of these keyword arguments to `subprocess.run()` when tar bytes were present:

```python
stdin=subprocess.PIPE
input=input_bytes
```

Python's subprocess contract rejects that combination and raises:

```text
ValueError: stdin and input arguments may not both be used.
```

The failure occurs before `docker container exec` starts. Because `ValueError` was outside the `SandboxDockerError` boundary, the Product emitted no bounded `tool.failed` Event and the SDK normalized it to `UserError`.

The exact failure was reproduced directly against the packaged STEP075C implementation with `sys.executable` as the subprocess executable and a stdin echo child.

## Impact

The tar-stream materializer could not start on any platform. Mock-based tests incorrectly accepted the invalid keyword combination, so deterministic acceptance did not detect the defect.

## Fix

1. With no input bytes, pass `stdin=subprocess.DEVNULL` and no `input` keyword.
2. With input bytes, pass `input=input_bytes` and no `stdin` keyword. `subprocess.run()` creates and owns the pipe.
3. Convert runner-configuration `ValueError` into bounded `SandboxDockerError` code `DOCKER_RUNNER_CONFIGURATION_INVALID`, operation identity and `INVALID_ARGUMENT` category without persisting the raw message.
4. Add a real subprocess stdin round-trip test using the active Python interpreter, not only a mock.
5. Keep the deterministic tar format, fixed root extractor, non-root read Tools, cleanup/orphan reconciliation and all Sandbox security boundaries unchanged.

## Automated recurrence prevention

- `tests/test_step075d_python_subprocess_stdin_input_contract_fix.py`
- real subprocess stdin round-trip
- mock assertion that `stdin` and `input` are mutually exclusive
- no-input DEVNULL contract
- bounded `ValueError` conversion
- STEP075D deterministic acceptance
- STEP075D Windows live acceptance

## Windows evidence after the fix

STEP075D live execution passed the subprocess boundary, Docker tar extraction and container reads, then failed at the distinct immutable hash-domain defect recorded as OR-ISSUE-005. This confirms the stdin/input fix itself reached its intended live boundary.
