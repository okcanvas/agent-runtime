# OR-ISSUE-074 — STEP084 source packager retained the STEP083 default filename

## Symptom

Pre-package inspection found that `scripts/package_source.py` declared the STEP084 Product identity but its `DEFAULT_OUTPUT` still named the STEP083 Organization Assistant archive.

## Code-confirmed root cause

The current STEP and configuration/reference packagers were promoted, while the Runtime source ZIP default path was omitted from the identity update.

## Impact

Invoking the packager without an explicit output could produce a STEP084 payload under a misleading STEP083 archive name and sidecar.

## Correction

The deterministic default Runtime archive is now `okcanvas-agent-runtime-step084-organization-knowledge-glossary-and-directory-foundation.zip`.

## Recurrence gate

- exact source packager identity regression;
- final Runtime ZIP artifact manifest;
- Fresh-ZIP identity and root validation.
