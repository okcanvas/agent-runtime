# Store replenishment review business cases

Canonical input/output packs for the commerce-shaped read-only Agent. Production runtime code does not import these fixtures.

- `case001-shortage`: mixed 12/7/0 shortage baseline, total 19.
- `case002-covered`: every SKU is covered, total 0, status `READY`, zero-quantity SKU ordering.
- `case003-tie-ordering`: equal reorder quantities prove SKU ascending tie-breaking.
- `case004-single-shortage`: exactly one shortage proves singular summary and mixed ordering.
- `case005-invalid-duplicate-sku`: invalid source payload; ingress must fail before preflight persistence.
- `case006-invalid-empty-items`: invalid source payload; zero inventory rows must not become a false `READY` result.
