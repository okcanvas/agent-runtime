# OR-ISSUE-071 — STEP084 acceptance referenced a nonexistent RuntimeInfo field

## Symptom

Direct execution of `scripts/run_step084_acceptance.py` stopped before writing JSON evidence with:

```text
AttributeError: 'RuntimeInfo' object has no attribute
'organization_context_default_catalog_state'
```

## Code-confirmed root cause

The STEP084 acceptance runner used `organization_context_default_catalog_state`, while the implemented and tested RuntimeInfo contract is `organization_context_catalog_default_state`.

## Impact

The Organization Context implementation and its focused tests passed, but the canonical integrated acceptance entrypoint could not complete or emit evidence.

## Correction

The acceptance runner now uses the exact RuntimeInfo field and validates the existing integrity/no-match blocking fields rather than referring to an unimplemented grounding flag.

## Recurrence gate

- `test_step084_acceptance_runtime_info_field_contract_is_exact`;
- direct STEP084 integrated acceptance;
- Windows launcher and Fresh-ZIP acceptance.
