# STEP062A — Windows Node Acceptance Portability Fix

## Baseline

- Project: `okcanvas-agent-runtime`
- Version: `2.42.1`
- STEP: `STEP062A_WINDOWS_NODE_ACCEPTANCE_PORTABILITY_FIX`
- State: `IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_RERUN_PENDING`

## Confirmed failure

The reported Windows STEP062 acceptance passed 27 of 29 checks. Every orchestration, policy,
Runtime-binding, Python, document and Reference check passed. Only Node build and Node tests failed.

The audited code had two Windows-specific defects:

1. `shutil.which("npm.cmd")` returned a Windows batch file and the Python subprocess path invoked it
   directly. The observed CP949 output tail corresponds to `배치 파일이 아닙니다.`.
2. `package.json` used `node --test test/*.test.mjs`. Windows CMD does not expand that glob, and Node
   received the literal path `test\\*.test.mjs`.

## Correction

- `scripts/node_acceptance.py` owns the cross-platform command boundary.
- On Windows, an npm script is executed through `cmd.exe /d /c call "<npm.cmd>" run <script>`.
- Node tests bypass shell glob expansion. Python enumerates and sorts the actual
  `test/*.test.mjs` files and passes each path directly to `node --test`.
- `package.json` also uses the cross-platform `node --test` discovery form.
- subprocess output is captured as bytes and decoded with UTF-8, platform locale and Windows
  fallback encodings so future diagnostics are not destroyed by a forced UTF-8 decode.

## Preserved boundary

No orchestration Runtime, policy, Agent definition, model call, Tool, MCP, Session, invocation,
Artifact, usage, cancellation or aggregation behavior changes. STEP063 remains unselected.

## Acceptance

Run:

```cmd
sh_run_step062a_acceptance.cmd
```

The gate reruns the complete corrected STEP062 29-check acceptance, verifies the exact Windows
command construction and explicit Node test-file enumeration, then checks compileall, TypeScript,
Node tests, documents and immutable References.
