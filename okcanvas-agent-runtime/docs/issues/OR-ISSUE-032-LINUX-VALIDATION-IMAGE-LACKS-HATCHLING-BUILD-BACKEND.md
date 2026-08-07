# OR-ISSUE-032 — Linux validation image lacks the configured Hatchling build backend

## Status

```text
EXTERNAL_ENVIRONMENT_BOUNDARY_DETERMINISTIC_CONTENTS_VALIDATED_WINDOWS_REAL_BACKEND_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

Both normal and no-build-isolation wheel commands failed before Product wheel creation:

```text
BackendUnavailable: Cannot import 'hatchling.build'
No matching distribution found for hatchling>=1.27
```

The active Linux interpreter does not contain Hatchling, and the configured validation package registry exposes no Hatchling release.

## Code-confirmed root cause

`pyproject.toml` correctly declares `hatchling.build` and `hatchling>=1.27`. Inspection of the active interpreter confirmed that the `hatchling` module is absent. A build-isolated `pip wheel` then confirmed the configured package registry cannot resolve any matching Hatchling distribution. This is an external validation-image/package-mirror limitation, not a Product source defect.

## Impact

The Linux environment cannot truthfully claim that the external Hatchling distribution itself built STEP081. Without an alternative executable validation, the mandatory wheel contents, fresh-wheel install, editable install, package-data, and console-entrypoint Gates would remain untested.

## Fix and bounded validation strategy

`scripts/validate_step081_installation.py` first detects whether real Hatchling is importable. When it is unavailable, the script creates a temporary, test-only PEP 517 module implementing the `hatchling.build` interface outside the Product tree. The shim reads the Product's real Hatch package allowlist, creates a standards-compliant installable wheel/editable wheel, and is destroyed after validation.

The validator then proves:

- wheel payload equals the three explicit Product Python package trees byte-for-byte;
- all ten relocated non-Python resources are present;
- tests, docs, reference, scripts, JavaScript Client workspaces, bytecode, and the temporary backend are absent;
- a fresh venv installs the wheel and imports all three packages from site-packages;
- Console/Runner resources resolve through `importlib.resources`;
- the installed console entrypoint executes;
- a second fresh venv performs PEP 660 editable installation and imports all three packages from the Product root.

This fallback validates Product package contents and install contracts but does not represent the external Hatchling implementation. Canonical Windows setup/live validation must repeat the install path with real configured dependencies.

## Recurrence-prevention gate

`STEP081_INSTALLATION_VALIDATION.json` records `backend_mode`, exact payload hashes, forbidden entries, fresh venv imports, editable paths, resource visibility, entrypoint output, and whether any temporary backend leaked into the wheel. STEP081 Compliance requires both installation Gates to pass and keeps `GATE-WINDOWS-LIVE` external until the real Windows dependency rerun.
