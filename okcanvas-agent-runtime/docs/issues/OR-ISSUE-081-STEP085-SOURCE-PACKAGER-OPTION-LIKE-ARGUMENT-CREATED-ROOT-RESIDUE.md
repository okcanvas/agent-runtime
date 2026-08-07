# OR-ISSUE-081 — STEP085 Source Packager Option-Like Argument Created Root Residue

## Status

```text
FIX_IMPLEMENTED_LOCAL_FINAL_FRESH_COMPLIANCE_ACCEPTED_WINDOWS_PENDING
```

## Symptom

Calling `package_source.py --output <path>` created archives literally named `--output` and `--help` in the repository root because the script accepts one positional output path and had no option-like argument rejection.

## Root cause

The packager's minimal positional CLI contract was not fail-closed for arguments beginning with `-`.

## Fix

Reject option-like or multiple arguments, remove the two root residue files and use the exact positional output contract.

## Recurrence gate

`test_source_packager_rejects_option_like_output`, Product inventory residue checks and the Fresh ZIP forbidden-entry Gate.
