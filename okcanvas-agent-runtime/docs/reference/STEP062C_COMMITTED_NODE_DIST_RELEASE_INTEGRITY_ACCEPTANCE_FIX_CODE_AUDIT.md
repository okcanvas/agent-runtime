# STEP062C Code Audit

## Audited baseline

- ZIP: `okcanvas-agent-runtime-step062b-windows-typescript-direct-compiler-portability-fix-v1.zip`
- Version: `2.42.2`
- STEP: `STEP062B_WINDOWS_TYPESCRIPT_DIRECT_COMPILER_PORTABILITY_FIX`
- Reported Windows result: `17/22 FAILED`

## Exact failure chain

### STEP062

The initial Windows gate passed all orchestration, Python, document and Reference checks, but failed Node build and Node tests. Node tests failed because Windows CMD did not expand `test/*.test.mjs`.

### STEP062A

Explicit Node test files fixed Node tests. `cmd.exe /d /c call npm.cmd run build` still returned:

```text
배치 파일이 아닙니다.
```

### STEP062B

The acceptance tried to locate a PATH `tsc` installation and execute its JavaScript compiler directly. The third Windows evidence proved that no `tsc` command existed:

```text
TypeScript compiler command not found on PATH
```

That assumption was not present in the package contract.

## Package contract found in code

`clients/okcanvas-agent-cli/package.json`:

- Node engine: `>=22.0.0`;
- runtime dependencies: none;
- development dependencies: none;
- executable bin: `./dist/cli.js`.

`clients/okcanvas-agent-cli/package-lock.json` contains only the root package.

`scripts/package_source.py` excludes `node_modules` but retains `clients/okcanvas-agent-cli/dist`.

`sh_tui.cmd` executes:

```text
node clients\okcanvas-agent-cli\dist\cli.js
```

Therefore:

```text
release creation: TypeScript compiler required
packaged product execution: TypeScript compiler not required
Windows release acceptance: external TypeScript compiler must not be assumed
```

## Reproduction evidence

The packaged TypeScript source was rebuilt with the available TypeScript `5.8.3` compiler. SHA-256 snapshots of all 21 files under `dist` were identical before and after the build.

The release manifest records:

- 11 exact input files;
- 21 exact compiled output files;
- 2 exact Node test files;
- compiler `typescript 5.8.3`;
- command `tsc -p tsconfig.json`;
- `dist_reproduced_byte_identical=true`;
- acceptance requires no external compiler, installation or network.

## Validation boundary

`scripts/node_acceptance.py::validate_committed_typescript_release` performs:

1. manifest schema/package/version validation;
2. zero-dependency package and lock validation;
3. exact input/output/test file-set and SHA-256 validation;
4. no `node_modules` and no `*.tmp` source residue;
5. exact `dist` shape: 7 `.js`, 7 `.d.ts`, 7 `.js.map`;
6. source-map file/source path validation;
7. `node --check` on every committed JavaScript file.

Node package tests remain a separate explicit execution gate.

## Preserved product code

No file under the following STEP062 implementation boundaries was changed for behavior:

```text
src/okcanvas_agent_runtime/orchestration/
src/okcanvas_agent_runtime/execution/
src/okcanvas_agent_runtime/invocations/
specs/agents/bounded-orchestration-*/
specs/policies/bounded-multi-agent-orchestration/
```

The current correction is acceptance/release-integrity only.
