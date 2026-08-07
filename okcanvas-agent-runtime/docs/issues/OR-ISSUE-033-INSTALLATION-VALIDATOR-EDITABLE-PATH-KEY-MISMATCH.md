# OR-ISSUE-033 — Installation validator compared editable output with the wrong JSON keys

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

The first complete STEP081 installation validation reported `15/16` with only:

```text
editable_imports_resolve_to_source: false
```

The captured editable import payload visibly contained the correct three canonical source paths.

## Code-confirmed root cause

The subprocess emitted JSON keys `runtime`, `protocols`, and `clients`, but the validator searched the raw string for keys named after the package directories (`okcanvas_agent_runtime`, `okcanvas_agent_protocols`, and `okcanvas_agent_clients`). The Product editable installation was correct; the evidence assertion addressed a different schema.

## Impact

A valid editable installation was falsely rejected. Had the raw substring check remained, formatting or key naming changes could also produce false results without validating the actual structured payload.

## Fix

The validator now parses the subprocess's final JSON line and compares the exact structured mapping:

```text
runtime   → <PROJECT_ROOT>/okcanvas_agent_runtime/__init__.py
protocols → <PROJECT_ROOT>/okcanvas_agent_protocols/__init__.py
clients   → <PROJECT_ROOT>/okcanvas_agent_clients/__init__.py
```

Wheel import isolation and resource visibility use the same parsed JSON evidence rather than substring matching.

## Recurrence-prevention gate

`scripts/validate_step081_installation.py` must complete all installation checks and emit `STEP081_INSTALLATION_VALIDATION.json` with exact structured editable paths, isolated wheel paths, and both packaged UI resources visible.
