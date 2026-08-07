# OR-ISSUE-016 — Service capabilities constitution snapshot was not initialized

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING
STEP: STEP080A_RATIFIED_ARCHITECTURE_CONSTITUTION_INTEGRATION_AND_COMPLIANCE_GATES
```

## Exact symptom

The first focused STEP080A Service API regression reached `GET /v1/service/capabilities` and raised:

```text
NameError: name 'architecture_constitution' is not defined
```

The response constructor referenced constitution identity fields, but the router composition function had not resolved the immutable constitution snapshot.

## Code-confirmed root cause

`service_clients/routes.py` resolved `CapabilityFoundationCatalog` during router construction but omitted the adjacent `resolve_architecture_constitution()` call. Static field-presence checks passed because the response fields and import existed; only the executable Service route test exposed the missing local binding.

## Impact

Any authenticated Service client requesting capabilities would receive an internal failure, so the constitution would not be discoverable through the public multi-user service boundary even though RuntimeInfo and AgentRuntimeBinding were correct.

## Fix

`build_service_client_router()` now resolves one immutable constitution snapshot at composition time and uses it for every capabilities response.

## Evidence

- `src/okcanvas_agent_runtime/service_clients/routes.py`
- `tests/test_step080_product_owned_capability_topology_and_tool_discovery_foundation.py`
- `tests/test_step069_multi_user_service_client_contract.py`
- `docs/evidence/STEP080A_VALIDATION.txt`

## Recurrence-prevention gate

The focused STEP080A regression executes the real FastAPI route and verifies the returned constitution identity, clause count, required Gate count, runtime-disabled source movement state and current STEP metadata. Field-presence-only tests are insufficient.
