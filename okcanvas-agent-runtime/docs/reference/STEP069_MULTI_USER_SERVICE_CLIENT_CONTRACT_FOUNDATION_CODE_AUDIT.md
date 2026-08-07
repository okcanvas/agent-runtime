# STEP069 code audit

## Audited baseline

The audit used the complete STEP068 ZIP. Before STEP069 the server had a large Control API but only
shared local `admin` and `submitter` keys. Searches across Product models, Session catalog,
Submission store, Attachment store and Control API found no `tenant_id`, `principal_id`, `user_id` or
resource ownership contract. All list and detail routes were global administrator views.

The existing `clients/okcanvas-agent-cli` sends both local administrator and Run-submitter keys and
opens `/v1/runs/{run_id}/sdk-stream`-adjacent development contracts. It is therefore not a safe final
service client.

## Selected design

STEP069 leaves all historical local administrator routes intact for development acceptance and adds
`/v1/service` instead of silently changing their semantics.

`ServiceClientTokenRegistry` parses an external JSON registry containing token SHA-256 values,
tenant, principal and roles. `ServiceClientAuthenticator` hashes each Bearer token in memory and does
constant-time comparison. The raw token and token ID are not written to Product state.

`SQLiteServiceResourceOwnershipStore` is additive and uses the existing Product DB only for the
ownership projection. It does not change Task/Run/Event/Artifact identities or allow clients to read
the database. Resources are keyed by type and ID and owned by tenant/principal.

`service_clients/routes.py` exposes only server API objects. It has no filesystem/workspace endpoint
and does not expose the native SDK stream. Artifact content is read through the existing verified
Artifact record and configured root checks, while storage paths remain private.

## Important findings

- Client idempotency must be principal-namespaced because the existing governed idempotency key is
  global.
- Run Artifact is not singular after Hosted Search and local Attachment evidence. Service clients
  need list and detail routes, so `ProductStore.list_artifacts(run_id)` was added.
- Approval is intentionally tenant-scoped rather than submitting-principal scoped, because the
  Approval Operator is a separate authority.
- Cross-scope access uses 404 to avoid resource existence disclosure.
- The persisted Event SSE is already durable and reconnectable. Native SDK stream is process-local
  and is not a service API.
- Skills must be introduced before final client implementation so clients can discover and render
  Skill capabilities without a later breaking API redesign.

## Source hashes at implementation

- `service-client-policy.json`: `693c2586778b3a6a15b4c8a0532f3e11aedce528973c4e4260d30f5ed1719f69`
- `service_clients/auth.py`: `b6719235374e07358dead5b4ef7206b68ecc3691a3d913b340df5877e5e4923d`
- `service_clients/ownership.py`: `aca56a258921c038fd43fbb4a5ff7c270944c6b06c2b96f67d76918930ea161a`

The route and contract hashes are recorded in final validation because they may change during review.

## Final source hashes

- `service_clients/routes.py`: `238579db7163e4f8ee48aee3cde59328ec7c91b6cc0a670d92b8bd0070491be3`
- `service_clients/contracts.py`: `d231fca22d645690d72052ed71489c8a7bf1925afec7ce384df6b2cc19abad2d`

The final deterministic suite also verifies that no `/v1/service` route exposes native SDK streaming,
workspace paths, storage paths or direct Runtime database access.
