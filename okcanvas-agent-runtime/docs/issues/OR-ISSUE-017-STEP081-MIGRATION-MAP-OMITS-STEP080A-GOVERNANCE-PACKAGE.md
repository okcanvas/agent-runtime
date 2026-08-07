# OR-ISSUE-017 — STEP081 migration map omitted the STEP080A governance package

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

The ratified `STEP081_PROJECT_LAYOUT_MIGRATION_MAP.json` reported 64 source entries from STEP080, while the actual immutable STEP080A source tree contained 65 first-level entries. The missing entry was:

```text
governance
```

The stale map could still pass the STEP080A constitution bundle hash validator because the validator proved that the committed annex was immutable, not that the annex still covered the current Product source.

## Code-confirmed root cause

STEP080A added `src/okcanvas_agent_runtime/governance/` after the STEP081 migration annex had been generated. No semantic freshness Gate compared the current source inventory with the migration map. File-hash consistency and current-source completeness were therefore incorrectly treated as the same property.

## Impact

A physical relocation driven only by the stale annex could omit the constitution runtime package and its two JSON resources while still claiming that the migration map was complete.

## Fix

- retained the ratified historical annex unchanged;
- generated `STEP081_SOURCE_BASELINE_INVENTORY.json` from the immutable STEP080A source tree;
- generated `STEP081_EXECUTED_RELOCATION_MANIFEST.json` for all 262 Python files and 10 resource files;
- required 65 first-level entries including `governance`;
- added a semantic STEP081 architecture validator and mutation regression that fail when `governance` is removed.

## Evidence

- `specs/architecture/STEP081_SOURCE_BASELINE_INVENTORY.json`
- `specs/architecture/STEP081_EXECUTED_RELOCATION_MANIFEST.json`
- `scripts/generate_step081_relocation_evidence.py`
- `scripts/validate_step081_architecture.py`
- `tests/test_step081_root_package_and_architecture_restructuring.py`

## Recurrence-prevention gate

`source_inventory_first_level_exact` requires exactly 65 source entries and the explicit `governance` member. `all_legacy_files_relocated` independently requires all 272 legacy files to resolve to canonical targets.
