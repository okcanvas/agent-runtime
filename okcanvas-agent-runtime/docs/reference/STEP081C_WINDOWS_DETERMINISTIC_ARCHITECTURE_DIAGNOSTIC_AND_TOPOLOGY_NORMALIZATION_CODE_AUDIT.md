# STEP081C code audit

## User-provided Windows evidence

```text
STEP081B deterministic Acceptance: FAILED 15/18
Architecture: 36/38
Launcher registry: PASS
Node/npm/Reference/portability: PASS
API or billing dependency: none
```

The output omitted the false Architecture check names and Compliance drift. The exact Windows Architecture sub-cause cannot be derived from the supplied output.

## Code changes

- `scripts/run_step081_acceptance.py`: isolated Architecture/Compliance subprocess execution and complete payload preservation.
- `scripts/validate_step081_architecture.py`: same-file project-root comparison.
- `scripts/step081_architecture.py`: source AST route inventory plus runtime `/v1` route reconciliation.
- `scripts/run_step081c_acceptance.py`: excluded local evidence output.
- `scripts/step081_product_inventory.py`: STEP081C local/live evidence exclusions.
- launcher registry and Windows entrypoint: STEP081C current identity.

## Promotion boundary

Deterministic and Fresh-ZIP validation can be completed without an API key. Windows live remains external and billing-dependent.

## Final code-derived verification

```text
source-declared Admin routes: 48
source-declared Service routes: 33
runtime HTTP routes: 86
missing runtime /v1 routes: 0
unexpected runtime /v1 routes: 0
method/path duplicates: 0
WebSocket routes: 0
project-root same-file failures: 0
```

Canonical STEP081C Acceptance preserves the complete Architecture and Compliance child-process payloads and passed 18/18. The fully Fresh-validated candidate passed Architecture 38/38, Compliance 16/16, Installation 16/16, Acceptance 18/18, and its protected executable/test payload is byte-identical to the candidate that completed Python 916/916.
