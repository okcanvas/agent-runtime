# OR-ISSUE-027 — Historical source-hash tests read removed physical files

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

STEP063A and STEP064A history regressions attempted to hash removed files such as `okcanvas_agent_runtime/sessions/encryption.py` and `okcanvas_agent_runtime/sessions/compaction.py`. They raised `FileNotFoundError` after the implementations moved to Adapter and Domain owners. A separate STEP061 assertion also dropped the historical `src/` prefix from immutable Windows evidence.

## Code-confirmed root cause

The tests treated the current physical source location as both the historical byte-evidence store and the active implementation. STEP081 intentionally changes implementation location and, where imports changed, canonical source bytes. Historical hashes belong to the immutable STEP080A baseline inventory, not to the relocated current file.

## Impact

Correct physical restructuring could not pass the historical regression suite. Recreating files at their old paths would violate `legacy_src_package_absent` and permit architecture drift. Altering historical evidence would falsify the accepted Windows record.

## Fix

- historical source hashes are resolved from `STEP081_SOURCE_BASELINE_INVENTORY.json`, generated from the immutable STEP080A baseline;
- non-relocated policy resources continue to be hashed from the current Product tree;
- the STEP060 Windows evidence assertion preserves its exact original `src/...` path string.

## Detailed evidence

All expected STEP063/STEP064 hashes exactly match the immutable baseline inventory, including encryption, compaction, session service, execution service, and approval service.

## Recurrence-prevention gate

The STEP063A and STEP064A regressions verify historical hashes through the signed STEP081 baseline inventory, while `source_inventory_hash_valid`, `all_legacy_files_relocated`, and `legacy_src_package_absent` prevent substitution with recreated legacy files.
