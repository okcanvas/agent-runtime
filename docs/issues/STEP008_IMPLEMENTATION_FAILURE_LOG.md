# STEP008 implementation failure and near-miss log

This file records implementation-time failures that did not become accepted product behavior.

## F-STEP008-001 — Inspection assumed nonexistent aggregate files

The first inspection command attempted to read `fixtures/tenant-a/records.json` and `src/resolver.ts`. Neither path exists. The actual fixture is split by entity collection and the resolver is `src/context-resolver.ts`.

Correction: enumerate the directory before opening files. No product source was changed by the failed command.

Recurrence gate: inspection scripts must discover concrete paths with `find`/inventory before reading guessed aggregate filenames.

## F-STEP008-002 — Architecture physical manifest was stale after Runtime edits

The first focused Runtime regression passed functional tests but failed architecture 39/40 because the physical module hash manifest still described pre-STEP089 source.

Correction: regenerate `STEP081_PHYSICAL_RELOCATION_MANIFEST.json` from the actual canonical module inventory, then rerun architecture 40/40.

Recurrence gate: every Runtime source edit must regenerate and validate the physical module manifest before current acceptance.

## F-STEP008-003 — Retained STEP084 test froze an obsolete archive basename

The first STEP089 acceptance run reached 102 passing tests and failed one stale assertion that still expected the STEP086R2 archive basename.

Correction: align the retained current-identity assertion with STEP089 and include it in STEP089 focused regression. Final focused regression passed 103/103.
