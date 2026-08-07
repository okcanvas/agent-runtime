# OR-ISSUE-097 — Current package filename regression froze STEP086R1

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_PENDING`

## Found in

`STEP086R2_DELEGATED_ROLE_HEADER_AND_EXTERNAL_CONNECTOR_CONTRACT_CLOSURE`

## Evidence

The first STEP086R2 bounded full Python regression reached the final chunk with 977 passing tests and one failure. A retained STEP084 test imported the current source packager but still required the superseded STEP086R1 archive name.

```text
expected: okcanvas-agent-runtime-step086r1-groupware-subagent-and-external-mcp-boundary-alignment.zip
actual:   okcanvas-agent-runtime-step086r2-delegated-role-header-and-external-connector-contract-closure.zip
```

## Root cause

The prior OR-ISSUE-094 correction updated a mutable current filename to the then-current literal instead of removing the historical test's ownership of current package identity. The same stale-current-literal failure therefore recurred at the next STEP promotion.

## Correction

- Aligned the retained current package assertion with the STEP086R2 package-source SOT.
- Kept STEP086R1 artifacts immutable and historical.
- Required final distribution validation to compare the generated basename with the current package-source SOT.
- Invalidated the bounded checkpoint through its test path/content SHA and restarted the full regression.

## Recurrence gate

- `tests/test_step084_organization_knowledge_glossary_and_directory_foundation.py`
- STEP086R2 content-hashed full Python regression
- STEP086R2 final distribution artifact basename check
