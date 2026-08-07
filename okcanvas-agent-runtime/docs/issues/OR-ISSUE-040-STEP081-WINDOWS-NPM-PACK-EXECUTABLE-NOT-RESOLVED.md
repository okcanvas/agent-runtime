# OR-ISSUE-040 — STEP081 Windows Acceptance did not resolve the npm batch executable

## Status

```text
WINDOWS_FIX_ACCEPTED_DISTINCT_LIVE_VALIDATOR_FAILURE_REMAINS
STEP: STEP081A_WINDOWS_NPM_COMMAND_RESOLUTION_AND_ACCEPTANCE_PORTABILITY
```

## Exact symptom

Running the packaged STEP081 deterministic launcher on Windows stopped before an Acceptance JSON was written:

```text
D:\NODE_AGENTS\okcanvas-agent-runtime>sh_run_step081_acceptance
FileNotFoundError: [WinError 2] 지정된 파일을 찾을 수 없습니다
```

The failing call was:

```python
subprocess.run(["npm", "pack", "--dry-run", "--json"], shell=False)
```

## Code-confirmed root cause

The STEP081 integrated Acceptance and non-Python validator bypassed the existing Windows Node portability helper and passed the bare command `npm` to `CreateProcess`. Standard Windows Node installations expose npm as `npm.cmd`. A `.cmd` file is a command-processor script, not a native executable, and must be invoked through `cmd.exe /d /c call` when Python uses `shell=False`.

Repository-wide inspection found one additional latent instance: `generate_node_cli_release_manifest.py` resolved `tsc.cmd` and passed that batch shim directly to `subprocess.run`.

## Impact

- STEP081 deterministic Windows Acceptance terminated with an uncaught traceback.
- No STEP081 Acceptance summary was produced.
- Node tests and `npm pack --dry-run` were not reached on Windows.
- The same command class could break TypeScript release-manifest generation.
- No model, Tool, Sandbox, Docker, persistence, or Product runtime operation occurred.

## Fix

1. Add `resolve_subprocess_command()` as the single Windows-aware subprocess command resolver.
2. Resolve bare executable names before launch.
3. Wrap every resolved `.cmd`/`.bat` through `cmd.exe /d /c call`.
4. Bound `OSError` and resolver failures into deterministic `(False, diagnostic)` results instead of allowing Acceptance to crash.
5. Add `run_npm_pack()` and require STEP081/STEP081A Acceptance and non-Python validation to use it.
6. Route TypeScript version discovery through the same portable runner.
7. Scan all Product scripts, Runtime, and Client Python sources for unsafe direct batch-shim subprocess calls.

## Recurrence-prevention gates

- `tests/test_step081a_windows_npm_command_resolution_and_subprocess_portability.py`
- `scripts/validate_windows_subprocess_portability.py`
- STEP081A deterministic Acceptance
- STEP081A Fresh-ZIP Acceptance
- Windows deterministic rerun through both compatibility and canonical STEP081A launchers

The real STEP081A Windows live run proved this command-resolution fix: the portability validator was 7/7, `windows_npm_pack_executes_through_resolver=true`, npm pack returned the complete 23-entry package, and no WinError traceback occurred. STEP081A still failed 75/77 for the distinct architecture-validator evidence defect recorded as OR-ISSUE-046.
