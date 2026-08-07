# OR-ISSUE-051 — STEP081C Windows runtime router registration diverged from source inventory

## Status

`FIX_IMPLEMENTED_DETERMINISTIC_VALIDATION_PENDING_WINDOWS_RERUN`

## Observed failure

The real Windows `sh_run_step081c_acceptance` result reported Architecture `36/38`. The complete diagnostic added by STEP081C proved that the source inventory still contained all expected routes:

- Admin source routes: 48
- Service source routes: 33
- Duplicate source routes: 0

The composed FastAPI runtime inventory in that validator process contained only the five direct development/health routes and no `/v1` routes:

- Admin runtime routes: 0
- Service runtime routes: 0
- Other runtime routes: 5
- Missing runtime `/v1` method/path pairs: 81

The exact reason why the two `include_router` calls did not result in registered routes in that Windows validator process is not proven by the retained evidence. It must not be guessed.

## Impact

The architecture validator correctly blocked promotion, but Product route registration still depended on a framework call without a Product-owned postcondition. Module source origins and the pre/post router registration counts were also not retained.

## Corrective implementation

STEP081D adds:

1. `include_router_exact()` as the Product-owned registration boundary.
2. Exact prebuilt router method/path inventory validation.
3. Normal `FastAPI.include_router()` as the primary path.
4. A bounded direct-route reconciliation only when the framework call returns with routes still missing.
5. Fail-closed final missing-route and duplicate-route checks.
6. Per-router registration evidence stored on `app.state`.
7. Exact module source-origin diagnostics for Runtime, Bootstrap, Admin/Service routes, Protocols and Clients.
8. Project root forced to the first import search path before validator imports.

## Recurrence gates

- `tests/test_step081d_windows_source_identity_router_registration_and_workspace_residue.py`
- `runtime_module_origins_exact`
- `router_registration_evidence_exact`
- `admin_route_inventory_exact`
- `service_route_inventory_exact`
- STEP081D deterministic and Windows acceptance
