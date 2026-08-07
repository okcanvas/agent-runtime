# STEP075A code audit

## Baseline reviewed

- STEP075 source ZIP SHA-256 `54578565b955c184cfbd86d235568943751ceb39484f12069ebb9f1db4396ca4`
- STEP075 Windows deterministic output: 28/28 PASS
- STEP075 Windows live output: 13/28 FAILED
- preserved workspace inventory supplied by the user

## Confirmed execution boundary

The first model turn completed and the SDK emitted `tool.started`. There was no `tool.completed`; the Run failed and retained its payload/workspace. The live summary did not expose the original Sandbox-specific code.

## Code finding

`src/okcanvas_agent_runtime/sandbox_runtime/read_only_workspace.py` used:

```python
tmpfs.get(workspace_path) == expected_tmpfs
```

This compares serialization rather than security meaning. Docker can normalize ordering, size notation, and Unix mode notation while preserving identical semantics.

## Adopted correction

- order-independent parser for comma-separated tmpfs options;
- byte-unit normalization for the exact 32 MiB limit;
- octal normalization for `0755`, `755`, and `0o755`;
- exact required flags and numeric ownership/mode values;
- fail-closed rejection of dangerous, missing, malformed, duplicate, or unknown options;
- bounded `tool.failed` lifecycle Event before the SDK can collapse the failure into a generic Run error.

## Preserved contracts

- Agent count 27; exactly one `sandbox-readonly-v1` Agent;
- exactly one read-only Sandbox Tool;
- same Sandbox policy/provider/foundation and Runtime binding identities;
- no SDK `SandboxAgent`, default capability composition, or SDK Docker client;
- no Shell, mutation, network, host mount, secret, image pull, resume, or Skill execution;
- cleanup and orphan-zero remain mandatory.

## Important uncertainty

The exact error code from the original STEP075 preserved database was not retrieved because the first diagnostic command used `database/` instead of `databases/`. Therefore the exact-string tmpfs comparison is a code-confirmed portability defect and high-probability failure point, but the original Windows failure is not retroactively claimed to be conclusively explained until STEP075A live rerun succeeds or reports its new exact bounded code.

## Reference decision

No upstream reference source was imported or modified. This fix concerns Product-owned Docker inspect validation and Product Event evidence, so the immutable Reference tree remains unchanged.

## Deterministic and package evidence

```text
STEP075A Acceptance: 31/31 PASS
Focused: 96/96 PASS
Historical: 47/47 PASS
Full Python: 806/806 PASS across 207 files
Candidate ZIP SHA-256: 9db7584a073f772587c658f36062b7b9e60a1b9dae178a1f2eff82931c24c913
Candidate canonical root / entries / forbidden: 1 / 3047 / 0
Candidate fresh acceptance / full Python: 31/31 / 806/806 PASS
```
