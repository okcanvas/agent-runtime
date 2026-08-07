# STEP062C — Committed Node Dist Release Integrity Acceptance Fix

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_RERUN_PENDING`

Version: `2.42.3`

## Trigger

The third real Windows run of `sh_run_step062b_acceptance.cmd` failed `17/22`.
The only executable failure remained the TypeScript acceptance build:

```text
TypeScript compiler command not found on PATH
```

Node tests passed. The corrected STEP062 and STEP062A failures were inherited from the same build prerequisite.

## Code-audited fact

`clients/okcanvas-agent-cli/package.json` and `package-lock.json` declare no runtime or development npm dependencies. The source ZIP excludes `node_modules`, while `sh_tui.cmd` executes committed `dist/cli.js` directly. Therefore external `tsc` is a release-production tool, not a declared Windows product or acceptance prerequisite.

The current source was rebuilt with TypeScript `5.8.3` using:

```text
tsc -p tsconfig.json
```

All 21 existing `dist` files remained byte-identical.

## Implemented correction

1. Add `clients/okcanvas-agent-cli/typescript-release-manifest.json`.
2. Bind exact SHA-256 values for 11 build inputs, 21 committed outputs and 2 Node test files.
3. Record the release compiler/version and byte-identical reproduction result.
4. On Windows acceptance, require no `tsc`, `npm install`, npm batch execution or network.
5. Verify manifest identity and every bound hash.
6. Verify source-map paths, exact compiled output shape and Node syntax for all committed JavaScript files.
7. Run the 14 Node tests with explicit sorted file paths.
8. Remove the zero-byte `src/config.ts.tmp` packaging residue.

## Non-goals

- no orchestration Runtime change;
- no Agent, policy, binding, Invocation, usage, Artifact or cancellation change;
- no TypeScript dependency addition;
- no vendored compiler;
- no npm install;
- no network or registry access;
- no STEP063 selection.

## Windows closure

```cmd
sh_run_step062c_acceptance.cmd
```
