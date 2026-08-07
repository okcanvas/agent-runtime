# OR-ISSUE-021 — Eager compatibility facades created package initialization cycles

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

After Store, Session, Gateway, and Runtime-binding implementations were moved, eager re-exports from package `__init__.py` files produced circular initialization among canonical packages.

## Code-confirmed root cause

Legacy public symbols and new implementation modules were initialized through the same eager facade. Importing a submodule first initialized its parent facade, which imported a dependent implementation before the original module had completed.

## Impact

Import order determined whether the same canonical module succeeded or raised a partially initialized module error.

## Fix

Affected facades use lazy symbol resolution, and legacy module names are served by the Product-owned meta-path alias registry. The canonical architecture graph separately evaluates executable module-initialization imports.

## Recurrence-prevention gate

`eager_import_cycles_absent` computes strongly connected components from module-level executable imports while excluding function-local and `TYPE_CHECKING` imports. The current graph has zero cycles.
