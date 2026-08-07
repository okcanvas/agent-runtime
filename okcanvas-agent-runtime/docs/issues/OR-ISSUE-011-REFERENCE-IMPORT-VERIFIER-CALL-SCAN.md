# OR-ISSUE-011 — Reference import verifier unbounded call-source extraction

## Status

`FIX_IMPLEMENTED_DETERMINISTIC_ACCEPTED`

## Exact symptom

During STEP078 packaging, the integrated deterministic acceptance repeatedly stopped inside the no-direct-reference-import verification and exceeded the 300-second process limit. The same acceptance components before that point had already completed successfully.

## Code-confirmed cause

`scripts/verify_no_reference_imports.py` parsed every Python file and called `ast.get_source_segment(...)` for every `ast.Call`, even when the file did not contain the only relevant path token, `reference/upstream`. The operation was unnecessary for the overwhelming majority of calls and made the repository-wide verifier scale with every call expression in all runtime and acceptance sources.

## Impact

The product runtime was not affected, but canonical deterministic acceptance and fresh-ZIP verification could stall after the source and live-acceptance scripts grew. That made the packaged evidence path unreliable.

## Fix

The verifier now performs call-source extraction only when the containing source file includes `reference/upstream`. Import and `ImportFrom` checks remain unchanged, and files containing the path token retain the original exact call inspection.

## Evidence

After the guard was added:

- `scripts/verify_no_reference_imports.py` reports `ok: true` and zero violations.
- STEP078 integrated deterministic acceptance completes and passes.
- The existing full-repository no-reference gate remains active.

## Automated recurrence gate

`tests/test_no_direct_reference_import.py::test_reference_verifier_skips_call_source_extraction_when_file_has_no_reference_token` replaces `_text` with a failing sentinel and proves ordinary files do not invoke expensive call-source extraction.
