# WORKSPACE-ISSUE-012 — E2E evidence command retained raw bearer

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_PENDING`

## Evidence

The first successful STEP003 E2E captured the Product CLI subprocess command verbatim. Although stdout, stderr and Runtime artifacts did not expose credentials, the persisted argv still contained the value following `--bearer`.

## Root cause

Secret-surface validation checked process output and Runtime records but not the acceptance harness's own command metadata.

## Correction

The E2E runner now replaces every value following `--bearer` with `[REDACTED]` before returning or writing evidence.

## Recurrence gate

STEP003 acceptance parses the E2E evidence and requires `[REDACTED]`, rejects all deterministic test-secret literals, and packages mutable E2E evidence outside the immutable file identity.
