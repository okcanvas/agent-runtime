# Service Client Token Registry V1

The server reads `OKCANVAS_SERVICE_CLIENT_TOKEN_REGISTRY_JSON` at process start. The JSON stores only
SHA-256 hashes of external Bearer tokens. Raw tokens are distributed to clients outside the Runtime
and must never be committed, logged, written to Product SQLite, or returned by any API.

```json
{
  "schema_version": "okcanvas-service-client-token-registry-v1",
  "tokens": [
    {
      "token_id": "alice-web",
      "token_sha256": "<64 lowercase hex characters>",
      "tenant_id": "tenant-a",
      "principal_id": "alice",
      "roles": ["agent-user"]
    }
  ]
}
```

Roles are exactly `agent-user` and `approval-operator` in V1. Multiple tokens may map to the same
principal. Resource ownership is stored by tenant and principal, never by token ID, so token
replacement does not orphan Product resources.
