# STEP075B_WINDOWS_DOCKER_COMMAND_OPERATION_EVIDENCE

```text
version: 2.55.2
state: IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING
```

## Trigger

STEP075A deterministic acceptance passed 31/31 on Windows, but the live run failed 13/29 after one
model turn and `tool.started`. The new bounded `tool.failed` Event proved
`DOCKER_COMMAND_FAILED/SandboxDockerError`, but did not identify the Docker operation, return code,
stderr class, or cleanup/orphan outcome. The preserved database confirmed the same limited payload.

## Scope

1. Retain all STEP075/075A security, workspace, tmpfs, Tool, Agent and Runtime-binding contracts.
2. Add a closed stable Docker operation vocabulary without persisting raw arguments.
3. Add integer return code, closed stderr category and output-truncation state.
4. Preserve the primary failure through forced cleanup and orphan reconciliation.
5. Attach cleanup attempted/completed and orphan count to the same bounded failure object.
6. Persist the bounded fields in `tool.failed`; never persist raw command, path, image, output,
   source content, exception message or secret.
7. Add OR-ISSUE-002 and deterministic/live recurrence gates.

## Explicit non-goals

- Do not guess or fix the still-unknown failing Docker command.
- Do not enable Shell, Apply Patch, network, mounts, secrets, Skill materialization or resume.
- Do not change Sandbox policy/provider contracts or the single read-only Agent/Tool graph.
- Do not hide cleanup failures or replace a primary operation failure with a later cleanup failure.

## Acceptance

- exact 2.55.2/STEP075B baseline and Windows rerun gate;
- STEP075A Windows failure summary exact, including missing operation evidence;
- operation vocabulary and stderr classification are closed and tested;
- failed image inspection records no cleanup required;
- failed workspace copy records operation, return code, category, completed cleanup and orphan zero;
- `tool.failed` contains bounded operation diagnostics and raw persistence flags false;
- STEP075/075A tmpfs and security regressions pass;
- full Python, Node, Reference and package integrity pass;
- deterministic Docker/network/model calls remain zero.
