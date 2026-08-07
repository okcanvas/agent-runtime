# Controlled commerce HTTP adapter

This is the only STEP025 adapter. It resolves a loopback base URL and bearer credential from local
environment variables, calls `GET /v1/inventory-snapshots/{snapshot_key}`, and accepts only a bounded
UTF-8 JSON response matching `StoreReplenishmentInput`.


## Snapshot identity

The returned `snapshot_id` must exactly equal the normalized requested `snapshot_key`. A mismatch fails before governed preflight with `COMMERCE_SNAPSHOT_IDENTITY_MISMATCH`.
