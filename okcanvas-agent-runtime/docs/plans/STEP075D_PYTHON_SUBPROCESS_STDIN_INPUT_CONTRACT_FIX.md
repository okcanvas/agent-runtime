# STEP075D — Python subprocess stdin/input contract fix

```text
STEP075D_PYTHON_SUBPROCESS_STDIN_INPUT_CONTRACT_FIX
version: 2.55.4
state: IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING
```

## Trigger

STEP075C Windows live acceptance failed after `tool.started` with no `tool.failed` Event. Direct execution of the packaged runner reproduced `ValueError: stdin and input arguments may not both be used.` The Docker process never started.

## Scope

- make `SubprocessDockerCommandRunner` pass `input` and `stdin` mutually exclusively;
- use DEVNULL for no-input commands and `input=bytes` alone for tar-stream commands;
- convert runner-configuration `ValueError` to bounded `DOCKER_RUNNER_CONFIGURATION_INVALID` evidence;
- add a real subprocess stdin round-trip regression test;
- preserve deterministic tar materialization, Docker security, read-only Tool behavior, hash verification and cleanup;
- add STEP075D deterministic/live Windows launchers and handoff evidence.

## Explicitly unchanged

- Sandbox policy and provider contract;
- deterministic GNU tar metadata;
- fixed root extractor command;
- non-root `find/cat/grep/tail` reads;
- network none, no ports/mounts/secrets/image pull;
- no Shell, Apply Patch, Skill materialization or host mutation.

## Acceptance

- exact STEP/version/gate and Windows launcher composition;
- STEP075C failure evidence and direct root-cause reproduction recorded;
- real subprocess stdin round-trip passes;
- mocks assert no simultaneous `stdin` and `input`;
- invalid runner configuration becomes bounded Product evidence;
- focused, historical, full Python, Node and Reference regression pass;
- deterministic Docker/network/model calls remain zero;
- Windows live workflow completes two model turns and one Sandbox Tool call.
