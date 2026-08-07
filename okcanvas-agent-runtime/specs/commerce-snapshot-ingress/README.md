# Commerce snapshot ingress

STEP025 permits one product-owned, read-only, loopback HTTP adapter. The adapter performs exactly
one explicit GET before governed Run preflight. It accepts only the strict
`StoreReplenishmentInput` contract, canonicalizes the validated snapshot, and binds adapter identity,
source-request hash, and snapshot hash into the existing encrypted submission fingerprint.

The source URL and bearer credential are injected from local environment variables. They are not
stored in adapter specifications, SQLite, Events, Artifacts, or source ZIPs. Redirects, retries,
model-selected endpoints, writes, remote hosts, and arbitrary HTTP are forbidden.


## Snapshot identity

The returned `snapshot_id` must exactly equal the normalized requested `snapshot_key`. A mismatch fails before governed preflight with `COMMERCE_SNAPSHOT_IDENTITY_MISMATCH`.
