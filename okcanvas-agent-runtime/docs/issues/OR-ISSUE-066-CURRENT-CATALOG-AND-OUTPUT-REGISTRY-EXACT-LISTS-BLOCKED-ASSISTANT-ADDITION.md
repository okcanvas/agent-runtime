# OR-ISSUE-066 — Current catalog and output-registry exact lists blocked Assistant addition

## Symptom

The first STEP083 full regression failed current-state tests: Operations Console required exactly 27 Agent definitions, while two output-runtime registry tests required the pre-STEP083 five-contract inventory.

## Code-confirmed root cause

Both tests represented current Product projections with exact additive inventories. STEP083 intentionally adds two Product Agents and `OrganizationAssistantResult`, but the projections' regression expectations were not moved with the catalog.

## Impact

The Product implementation and runtime registry were correct, but cumulative regression could not accept the new Assistant surfaces.

## Correction

Current-state expectations now require 29 Agent definitions and the six-contract output registry including `OrganizationAssistantResult`. Historical STEP081D live evidence remains unchanged.

## Recurrence gate

- `tests/test_operations_console_api.py`;
- `tests/test_output_contract_runtime_registry.py`;
- full STEP083 Python regression.
