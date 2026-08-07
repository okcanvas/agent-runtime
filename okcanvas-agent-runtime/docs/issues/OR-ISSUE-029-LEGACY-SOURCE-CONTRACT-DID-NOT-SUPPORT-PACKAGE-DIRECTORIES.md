# OR-ISSUE-029 — LegacySourceContract did not support historical package directories

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

`legacy_source_contract(ROOT, "okcanvas_agent_runtime/skills").is_dir()` raised `KeyError` after Skills moved to `okcanvas_agent_runtime/agent/skills`. File and asset compatibility worked, but package-directory compatibility did not.

## Code-confirmed root cause

The resolver accepted only `.py` logical paths and a small static-asset prefix set. It already knew the package alias `okcanvas_agent_runtime.skills -> okcanvas_agent_runtime.agent.skills`, but rejected the request before alias resolution.

## Impact

Historical feature checks and downstream source-introspection code could not prove that relocated package capabilities still exist without recreating removed directories.

## Fix

The resolver now accepts historical Runtime package paths, follows the existing alias chain to the canonical `__init__.py`, and exposes `is_dir()`/`exists()` semantics without recreating a legacy package tree.

## Recurrence-prevention gate

STEP069 Skill visibility regression resolves the historical Skills package as a directory, while alias completeness and target Gates guarantee the canonical package exists.
