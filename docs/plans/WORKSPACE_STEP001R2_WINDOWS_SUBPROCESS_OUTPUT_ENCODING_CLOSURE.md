# WORKSPACE STEP001R2 — Windows subprocess output encoding closure

## Scope

Correct only the Workspace management subprocess capture boundary found by the user's real Windows
run. Preserve Runtime, Product CLI, Connector, and Example source bytes.

## Corrections

1. Capture child stdout/stderr as bytes instead of locale-decoded text.
2. Decode UTF-8 output before attempting the Windows preferred encoding.
3. Retain CP949 support for Python or native child processes that use the Windows locale.
4. Fall back to replacement decoding so subprocess reader threads cannot terminate acceptance.
5. Record the selected stdout/stderr encoding in structured evidence.
6. Forward STEP001 and STEP001R1 launchers to the corrected STEP001R2 runner.

## Non-goals

- No Product Service CLI execution implementation.
- No Organization Entity Resolver implementation.
- No Runtime, Connector, or Example product source modification.
