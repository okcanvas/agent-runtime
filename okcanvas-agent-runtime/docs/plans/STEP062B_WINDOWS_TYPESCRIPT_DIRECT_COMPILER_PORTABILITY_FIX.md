# STEP062B — Windows TypeScript Direct Compiler Portability Fix

- Project: `okcanvas-agent-runtime`
- Version: `2.42.2`
- STEP: `STEP062B_WINDOWS_TYPESCRIPT_DIRECT_COMPILER_PORTABILITY_FIX`
- State: `IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_RERUN_PENDING`

## Evidence that selects this STEP

The first STEP062 Windows run passed 27/29. STEP062A corrected the Node test glob and attempted to
run `npm.cmd` through `cmd.exe /d /c call`. The second reported Windows run passed 16/18, and its
embedded STEP062 gate passed 28/29. Node tests, focused Python tests and compileall passed. The only
remaining executable defect was TypeScript build, again reporting `배치 파일이 아닙니다.`.

Therefore the `npm.cmd` batch boundary is rejected for acceptance builds. This conclusion is based
on the two reported JSON results, not on an inferred Windows shell behavior.

## Scope

1. Keep the existing CLI source, committed `dist/`, package scripts and zero runtime dependency
   contract unchanged.
2. Resolve the existing PATH `tsc` command.
3. If it is a Windows npm shim such as `<prefix>/tsc.cmd`, resolve and filesystem-verify the actual
   JavaScript compiler at `<prefix>/node_modules/typescript/bin/tsc` (with bounded compatible
   candidates).
4. Run exactly `node <verified compiler JS> -p tsconfig.json` with a subprocess argument vector.
5. Keep Node tests as explicit sorted files.
6. Make STEP062 and STEP062A acceptance use the direct compiler helper.
7. Record the second Windows failure and add a STEP062B gate.

## Non-scope

- no orchestration Runtime change;
- no Agent, policy, binding, Invocation, Artifact, usage, cancellation or aggregation change;
- no npm install, registry access or new dependency;
- no vendored TypeScript compiler;
- no change to product target execution, which uses committed `dist/` and does not require
  TypeScript;
- no STEP063 selection.

## Required acceptance

```cmd
sh_run_step062b_acceptance.cmd
```

The gate must show that corrected STEP062A passes 18/18, corrected STEP062 passes 29/29, the direct
compiler command contains no `.cmd` or `.bat`, TypeScript build passes, Node tests pass 14/14,
References remain unchanged and STEP063 remains unselected.
