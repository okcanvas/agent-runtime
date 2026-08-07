# OR-ISSUE-094 — Current package filename regression froze STEP086

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_PENDING`

## Found in

`STEP086R1_GROUPWARE_SUBAGENT_AND_EXTERNAL_MCP_BOUNDARY_ALIGNMENT`

## Evidence

The bounded full Python regression completed 11/12 chunks with 865/865 passing tests. The final chunk failed one retained STEP084 assertion because it imported the current `scripts.package_source.DEFAULT_OUTPUT` and still required the superseded STEP086 archive filename, even though `PACKAGE_STEP` had already advanced to STEP086R1.

```text
expected: okcanvas-agent-runtime-step086-groupware-read-only-vertical.zip
actual:   okcanvas-agent-runtime-step086r1-groupware-subagent-and-external-mcp-boundary-alignment.zip
```

## Root cause

A historical feature test owned the mutable current distribution filename instead of validating the current package identity through the package-source SOT. This is the same stale-current-literal class previously seen in OR-ISSUE-026, OR-ISSUE-041 and OR-ISSUE-087.

## Correction

- Updated the retained assertion to the STEP086R1 current archive identity.
- Kept historical STEP086 artifacts and launchers historical; no old artifact was renamed in place.
- Re-ran the failed bounded chunk after the correction.

## Recurrence gate

- Full bounded Python regression must include all current packaging identity assertions.
- Final distribution validation must compare the generated runtime archive basename with `scripts.package_source.DEFAULT_OUTPUT.name`.
- A STEP promotion must update the package-source SOT and current-identity regression together.
