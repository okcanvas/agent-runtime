# WORKSPACE-ISSUE-007 — Windows subprocess output used CP949 text decoding

## Failure

The real Windows Workspace STEP001R1 run resolved `npm.cmd` correctly, but `run_process()` used
`subprocess.run(..., text=True, capture_output=True)` without an explicit encoding. Python therefore
created CP949 text readers for the captured pipes. A Node/npm child emitted UTF-8 bytes containing
`0xE2`, and the background reader thread raised `UnicodeDecodeError` before acceptance evidence could
be produced.

## Correction

Capture stdout and stderr as bytes. Decode each stream by trying UTF-8 first, then the Windows/platform
preferred encoding, then replacement decoding. Record the selected encoding in every process result.
The acceptance runner also performs direct UTF-8 and CP949 probes before executing child projects.

## Recurrence gates

- Unit-test UTF-8 output while the simulated preferred encoding is CP949.
- Unit-test CP949 Korean output fallback.
- Unit-test malformed bytes never raise.
- Forbid `text=True` in the shared Workspace subprocess runner.
- Run the corrected Workspace acceptance on real Windows before promotion.
