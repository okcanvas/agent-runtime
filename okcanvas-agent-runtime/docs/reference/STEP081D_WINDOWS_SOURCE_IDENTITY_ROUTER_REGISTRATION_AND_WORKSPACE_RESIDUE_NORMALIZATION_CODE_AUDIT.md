# STEP081D code audit

## Proven Windows failure

The supplied STEP081C Acceptance preserved complete diagnostics and proved two independent deterministic failures:

1. Source inventory contained Admin 48 and Service 33 routes, but the composed runtime application contained only five non-`/v1` routes and zero Admin/Service routes.
2. Compliance saw 14 non-Product paths that were not in the protected inventory.

The exact external trigger that caused ordinary `include_router` behavior to yield zero `/v1` routes was not observed. STEP081D does not assign an unsupported cause.

## Product changes

### Router registration ownership

`okcanvas_agent_runtime/bootstrap/router_registration.py` adds `include_router_exact()`.

The helper:

- requires a non-empty router declaration inventory;
- rejects duplicate method/path declarations;
- calls the normal FastAPI `include_router` path first;
- measures the actual application registrations;
- appends only still-missing declared `APIRoute` objects as a bounded reconciliation fallback;
- fails closed if expected routes remain missing or duplicates appear;
- records owner, expected count, registered count, fallback use, missing routes, and duplicates in `app.state.router_registration_evidence`.

`bootstrap/application.py` uses the helper for both Service and Admin routers.

### Source identity

`scripts/project_source_identity.py`:

- places the selected project root first in `sys.path` and subprocess `PYTHONPATH`;
- resolves module/object origins;
- verifies key modules originate under the current project tree.

Architecture evidence now includes runtime module origins, Python/framework versions, router-registration evidence, and source/runtime route reconciliation.

### Workspace residue

`scripts/step081_product_inventory.py` classifies and excludes only known non-Product residue categories:

- superseded local STEP081B regression logs;
- root-local historical archive/sidecar files;
- root-local `yarn.lock`.

Unknown Product or executable additions still fail exact changed-file validation.

### Identity SOT

`ServiceUseCases` no longer owns a duplicated pending-step string. The Service capabilities response obtains `next_selected_step` from `RuntimeInfo`.

## Final code-derived state

```text
source Admin routes: 48
source Service routes: 33
runtime Admin routes: 48
runtime Service routes: 33
other HTTP routes: 5
missing runtime /v1 routes: 0
unexpected runtime /v1 routes: 0
route duplicates: 0
WebSocket routes: 0
module-origin failures: 0
router-registration evidence failures: 0
Architecture: 40/40 PASS
Compliance: 17/17 PASS
Acceptance: 18/18 PASS
Installation: 16/16 PASS
Python: 230 files, 921/921 PASS
Fresh Python: 230 files, 921/921 PASS
```
