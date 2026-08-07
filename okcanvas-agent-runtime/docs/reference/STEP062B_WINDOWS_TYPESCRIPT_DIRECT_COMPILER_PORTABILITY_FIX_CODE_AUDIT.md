# STEP062B Windows TypeScript Direct Compiler Portability Fix — Code Audit

## Audited evidence

The user-reported STEP062A Windows result was:

```text
STEP062A 16/18
corrected STEP062 28/29
FAILED corrected_step062_acceptance_pass
FAILED node_typescript_build_pass
node_build_output_tail = 배치 파일이 아닙니다.
node_tests_pass = true
```

This proves that the STEP062A Node test correction worked, while the `npm.cmd` build boundary still
did not. The failure is preserved verbatim in
`docs/evidence/STEP062A_WINDOWS_TYPESCRIPT_BUILD_FAILURE_SUMMARY.json`.

## Existing package contract

`clients/okcanvas-agent-cli/package.json` has zero runtime dependencies and the source ZIP contains
compiled `dist/`. Product execution therefore does not need TypeScript. Development validation has
historically used the TypeScript compiler already available on PATH. STEP062B preserves that
contract and does not add network installation or a package dependency.

## Corrected build path

`scripts/node_acceptance.py` now implements:

```text
PATH tsc resolution
→ local project compiler candidates
→ PATH shim/symlink candidates
→ Windows npm global layout candidates
→ filesystem verification of a non-batch compiler entrypoint
→ node <compiler> -p tsconfig.json
```

For the normal Windows npm global layout:

```text
<prefix>\tsc.cmd
<prefix>\node_modules\typescript\bin\tsc
```

The first path is used only to locate the prefix. It is never executed. The subprocess command is an
argument list and contains neither `.cmd` nor `.bat`.

## Exact production files changed

- `scripts/node_acceptance.py`
- `scripts/run_step062_acceptance.py`
- `scripts/run_step062a_acceptance.py`
- `scripts/run_step062b_acceptance.py`
- `sh_run_step062b_acceptance.cmd`
- current baseline/version metadata and tests
- STEP062B plan, evidence, audit and handoff documents

No file under the STEP062 orchestration implementation, Agent specs or policy specs was changed.

## Rejected alternatives

- another `cmd.exe` quoting variation: rejected because the second real Windows result already
  disproved the batch-boundary correction;
- `npx.cmd`: rejected because it is another Windows batch wrapper and may introduce registry access;
- adding TypeScript and running npm install: rejected because it changes setup and package
  dependency policy;
- skipping compilation or checking only committed `dist/`: rejected because it would weaken the
  existing TypeScript source validation.

## Closure rule

Only a real Windows `sh_run_step062b_acceptance.cmd` result can mark this correction and STEP062
Windows-live accepted. Until then both live flags remain false and STEP063 remains unselected.
