# OR-ISSUE-020 — Prefix-based import rewrite changed an unrelated module

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

A rewrite rule intended for:

```text
sessions.rotation
```

also changed the distinct module:

```text
sessions.rotation_policy
```

This produced a missing internal import after relocation.

## Code-confirmed root cause

The first migration pass used raw text-prefix replacement instead of complete Python module-name matching. The shorter module name was a prefix of a valid sibling module.

## Impact

A syntactically valid file could import a nonexistent target, and similar prefix collisions could silently redirect future modules.

## Fix

All current internal imports are parsed as Python AST module names and resolved against the canonical module inventory plus the compatibility alias registry. Relocation evidence is generated from exact legacy paths through `LegacySourceContract` rather than raw prefix substitution.

## Recurrence-prevention gate

`internal_import_targets_complete` validates every internal import target; `physical_module_inventory_current` detects target drift; full canonical module import regression remains required before STEP081 closure.
