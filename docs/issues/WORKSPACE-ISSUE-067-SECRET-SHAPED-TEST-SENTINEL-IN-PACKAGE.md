# WORKSPACE-ISSUE-067 — Secret-shaped test sentinel in package

## Status

FIXED_IN_R11_RELEASE_VALIDATION

## STEP

Workspace R11 / Runtime STEP096A

## Observation

Fresh package scanning found one OpenAI-key-shaped `sk-...` literal in a historical SQLite negative persistence test. Inspection confirmed the value was a synthetic sentinel, but its shape was unnecessary and made release secret scanning ambiguous.

## Correction / recurrence gate

The test now uses a non-secret-shaped sentinel with unchanged persistence semantics. The R11 static gate scans the source/package inventory for OpenAI-key-like, AWS-AKIA-like and private-key-block literals in addition to excluding local environment files.
