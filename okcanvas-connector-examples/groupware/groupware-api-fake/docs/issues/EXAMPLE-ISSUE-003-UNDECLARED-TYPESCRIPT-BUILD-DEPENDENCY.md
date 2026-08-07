# EXAMPLE-ISSUE-003 — Undeclared TypeScript build dependency

## Evidence

A clean Windows extraction failed before tests:

```text
'tsc' is not recognized as an internal or external command
```

The package invoked `tsc -p tsconfig.json`, but `devDependencies` was empty and no lockfile existed.
Prior acceptance inherited a global compiler and therefore did not prove a clean-workspace setup.

## Correction

- bump the example lineage to `EXAMPLE_STEP001R1_TYPESCRIPT_BUILD_DEPENDENCY_CLOSURE` / `0.1.1`;
- declare exact TypeScript `5.8.3` as a local file devDependency;
- retain `package-lock.json`;
- vendor `vendor/typescript-5.8.3.tgz`;
- run deterministic offline `npm ci` before tests and acceptance;
- validate the dependency, lock and vendored tarball in acceptance.

## Recurrence gate

A clean extraction with no global `tsc` must pass:

```cmd
npm test
npm run acceptance
```
