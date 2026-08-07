# Governed commerce snapshot ingress

## Purpose

STEP025 supplies the existing `store-replenishment-review-agent` with a real externally read snapshot without moving source-of-truth acquisition into the model or Agent Tool loop.

## API

```http
POST /v1/commerce-snapshot-ingress/preflight
```

Request fields:

```json
{
  "source_adapter_id": "controlled-commerce-http",
  "snapshot_key": "case001-shortage",
  "model": "configured-model",
  "idempotency_key": "caller-owned-unique-key"
}
```

The Agent ID is intentionally fixed by the server. The caller cannot provide a URL, HTTP method, headers, credential, output contract, or alternate Agent.

## Source contract

The source must expose:

```text
GET /v1/inventory-snapshots/{snapshot_key}
Authorization: Bearer <environment-injected credential>
Accept: application/json
```

The returned JSON must match `StoreReplenishmentInput`. Unknown fields, duplicate keys, invalid UTF-8, negative units, an empty item set, duplicate SKUs, excessive size, and more than 100 items fail before submission creation.

## Security properties

- loopback literal IP only;
- no redirects;
- no retry;
- no proxy/environment trust in the HTTP client;
- exact bounded response;
- no raw source response in SQLite or Events;
- no source credential in Product state;
- no Task/Run until encrypted protected input and exact challenge exist;
- same idempotency replay cannot silently acquire a changed snapshot.

## Non-scope

Remote ERP access, arbitrary HTTP, write operations, purchase orders, inventory mutation, model-selected sources, multiple adapters, and connector marketplaces are not implemented.

## Windows live acceptance

The controlled Windows acceptance passed all 21 checks. The source was read once, no write method was called, replay did not read again, the exact snapshot identity remained bound through confirmation, and the resulting Run, Artifact, Evaluation, retention, Reference, and cleanup evidence all passed.


## Snapshot identity

The returned `snapshot_id` must exactly equal the normalized requested `snapshot_key`. A mismatch fails before governed preflight with `COMMERCE_SNAPSHOT_IDENTITY_MISMATCH`.
