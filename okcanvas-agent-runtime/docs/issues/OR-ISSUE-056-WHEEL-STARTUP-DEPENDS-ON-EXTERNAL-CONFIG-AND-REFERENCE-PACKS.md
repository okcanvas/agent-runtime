# OR-ISSUE-056 — Wheel startup depends on external Product configuration and immutable Reference packs

## Symptom

The wheel declared only the three Python packages. A fresh installed wheel could import and show CLI help, but full `create_app()` startup failed when its selected `project_root` lacked Product configuration.

## Code-confirmed root cause

Runtime catalogs load definitions and policies from `project_root/specs`. Session policy integrity also validates pinned SDK source under `project_root/reference`. Neither root is included in the wheel package allowlist.

## Exact startup evidence

- Full source root: PASS.
- Installed wheel only: fails closed with `SessionPolicyError` because configuration is missing.
- Installed wheel + `specs`: fails closed with `SessionPolicyError` because pinned Reference source is missing.
- Installed wheel + configuration pack + Reference pack: PASS.

## Correction

STEP082B defines three explicit artifacts: Runtime wheel, Product Configuration Pack, and immutable Reference Pack. The latter two can be materialized into one composite runtime root without copying them into the wheel.

## Recurrence gate

- `specs/distribution/product-artifact-boundaries.json`
- `scripts/package_product_configuration_pack.py`
- `scripts/package_reference_pack.py`
- `scripts/validate_step082b_distribution.py`.
