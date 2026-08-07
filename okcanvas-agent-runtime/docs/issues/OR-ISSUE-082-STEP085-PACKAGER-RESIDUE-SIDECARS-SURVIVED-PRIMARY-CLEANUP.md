# OR-ISSUE-082 — STEP085 Packager Residue Sidecars Survived Primary Cleanup

## Status

```text
FIX_IMPLEMENTED_LOCAL_FINAL_FRESH_AND_COMPLIANCE_ACCEPTED_WINDOWS_PENDING
```

## Symptom

After the option-like archives `--output` and `--help` were removed, their root SHA-256 sidecars `--output.sha256` and `--help.sha256` remained in the working tree.

## Root cause

The OR-ISSUE-081 cleanup and recurrence assertion enumerated only the primary archive names and did not treat option-like sidecars as the same residue family.

## Fix

Remove the two sidecars, assert the absence of all four residue names, and classify any ZIP entry whose basename begins with `--` as forbidden.

## Recurrence gate

`test_source_packager_rejects_option_like_output`, STEP085 Fresh ZIP option-like basename rejection, source-root residue inspection and final artifact manifest verification.
