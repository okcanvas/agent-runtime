# OR-ISSUE-087 — Historical packager test retained the STEP085 archive name

## Status

`FIX_IMPLEMENTED_LOCAL_FINAL_FRESH_AND_COMPLIANCE_ACCEPTED_WINDOWS_PENDING`

## Discovered in

`STEP086_GROUPWARE_READ_ONLY_VERTICAL`

## Failure

The source packager correctly declared STEP086 and emitted the STEP086 archive filename, but a preserved STEP084 regression still required the STEP085 archive name.

## Root cause

The test mixed a permanent packager identity invariant with a temporary current artifact filename. The package step assertion had already advanced, while the filename literal had not.

## Correction

The current packager identity test now requires the exact STEP086 archive name:

`okcanvas-agent-runtime-step086-groupware-read-only-vertical.zip`

## Recurrence gate

- `tests/test_step084_organization_knowledge_glossary_and_directory_foundation.py`
- `scripts/package_source.py`
- STEP086 final artifact manifest
