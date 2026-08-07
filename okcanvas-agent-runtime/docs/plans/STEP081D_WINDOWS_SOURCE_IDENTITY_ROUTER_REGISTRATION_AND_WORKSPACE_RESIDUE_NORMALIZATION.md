# STEP081D Windows source identity, router registration, and workspace residue normalization

```text
STEP081D_WINDOWS_SOURCE_IDENTITY_ROUTER_REGISTRATION_AND_WORKSPACE_RESIDUE_NORMALIZATION
version: 2.61.4
```

## Triggering Windows evidence

The real STEP081C deterministic Windows result was local and billing-independent:

```text
state: FAILED
passed_checks: 15/18
Architecture: 36/38
false Architecture checks:
  admin_route_inventory_exact
  service_route_inventory_exact

source-declared routes:
  Admin: 48
  Service: 33

runtime-registered routes:
  Admin: 0
  Service: 0
  Other HTTP: 5
```

The same run also found 14 paths outside the protected Product inventory: twelve superseded STEP081B regression logs, one root-local historical ZIP, and `yarn.lock`.

The evidence proves the source/runtime registration divergence and workspace residue. It does not prove why the ordinary FastAPI `include_router` call produced no `/v1` registrations in that Windows validation process. That unobserved environmental trigger must not be guessed.

## Scope

- Make Admin and Service router registration a Product-owned, fail-closed composition contract.
- Reconcile only missing declared `APIRoute` objects when ordinary router inclusion leaves expected routes absent.
- Preserve registration evidence on the composed application.
- Force the current project root to the front of Python module resolution for deterministic validators.
- Verify origins of the key bootstrap, transport, application, and architecture modules.
- Separate known non-Product workspace residue from Product changed-file inventory.
- Remove duplicated Service-capabilities STEP identity and read it from `RuntimeInfo`.
- Preserve complete Architecture and Compliance subprocess diagnostics.

## Non-scope

- No model, Tool, Sandbox, REST contract, persistence, authorization, or client authority change.
- No WebSocket activation.
- No claim that a specific external Python package or Windows environment caused the STEP081C route loss.
- No official promotion without the required Windows evidence.

## Completed deterministic and Fresh validation

```text
Architecture: 40/40 PASS
Windows subprocess portability: 7/7 PASS
Python files: 230
Python tests: 921/921 PASS
Node: 14/14 PASS
Reference: 4/4 PASS
Installation: 16/16 PASS
Compliance: 17/17 PASS
Acceptance: 18/18 PASS
Fresh ZIP Python: 921/921 PASS
Fresh route inventory: Admin 48, Service 33, Other 5
```

Windows deterministic Acceptance does not require an OpenAI API key or billing credit. Windows live remains an external gate while billing/API access is unavailable.
