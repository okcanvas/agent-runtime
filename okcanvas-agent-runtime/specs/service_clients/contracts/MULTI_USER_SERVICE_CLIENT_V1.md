# Multi-user Service Client Contract V1

## Product boundary

OKCanvas Agent Runtime is a multi-user server. It owns Agent execution, Product Session state,
Submission, Run, persisted Event, Approval, Artifact, Attachment, MCP, Hosted Tool and future Skill
state. A service client is never an embedded Runtime.

The service API prefix is `/v1/service`. Planned clients are:

- `agent-cli/`
- `agent-web/`
- `agent-desktop/`

The current `/runner`, `/console`, Python TUI and `clients/okcanvas-agent-cli` are development and
acceptance-test harnesses. Their local administrator credentials and process-local SDK stream are not
service-client contracts.

## Authentication

Clients send `Authorization: Bearer <external token>`. The Runtime configuration stores only token
SHA-256 values in `OKCANVAS_SERVICE_CLIENT_TOKEN_REGISTRY_JSON`. The token registry maps each token
to immutable `tenant_id`, `principal_id` and roles. Raw bearer tokens are never persisted.

V1 roles are exactly:

- `agent-user`
- `approval-operator`

## Ownership

The server records an additive SQLite ownership projection for:

- attachment slot;
- Product Session;
- Run Submission;
- Product Task;
- Product Run;
- Tool Approval.

Agent users can access only resources owned by the same tenant and principal. Approval operators can
read and decide Approval resources belonging to their tenant but do not inherit access to the
submitting principal's Session, Submission, Run or Artifact.

Cross-principal and cross-tenant resource access returns `404` so the API does not disclose whether a
resource exists.

## Idempotency

A client-provided idempotency key is namespaced with tenant and principal using SHA-256 before it is
passed to the existing governed Submission boundary. The same client key may therefore be used by
different principals without collision.

## Streaming and Artifacts

Service clients use persisted Run Event SSE and reconnect with `Last-Event-ID`. The process-local
native SDK stream is deliberately absent from `/v1/service`.

A Run can have multiple Artifacts. Service clients list `/runs/{run_id}/artifacts` and retrieve one
verified JSON Artifact by ID. They do not receive storage paths.

## Forbidden client access

A service client must not:

- import Runtime Python modules;
- read or write Runtime SQLite;
- open Runtime workspaces or Artifact directories;
- access encrypted attachment, Session, protected-payload or RunState files;
- receive local administrator, Run-submitter, provider or encryption keys;
- depend on native SDK objects or process-local streams.

## Skill status

Skill execution is not implemented in STEP069. `/v1/service/capabilities` reports
`skills_available=false` and selects `STEP070_PRODUCT_OWNED_SKILL_PACKAGE_FOUNDATION_V1` as the next
foundation step.

## Product-owned Skill catalog after STEP070

Authenticated service clients may discover immutable server-installed Skill metadata through
`GET /v1/service/skills` and `GET /v1/service/skills/{skill_id}`. Responses expose hashes,
resource metadata, allowed Agent IDs and required capability identities, but never instruction or
resource content. Clients cannot upload, modify, install, enable, disable or execute a Skill
independently; they submit an Agent that explicitly binds the Skill.
