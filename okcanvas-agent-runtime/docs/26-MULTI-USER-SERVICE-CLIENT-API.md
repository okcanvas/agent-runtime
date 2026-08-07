# Multi-user service client API

## Configure service principals

Generate a high-entropy bearer token outside the Runtime and calculate its SHA-256. Configure the
server with a JSON registry that contains only the hash:

```cmd
set "OKCANVAS_SERVICE_CLIENT_TOKEN_REGISTRY_JSON={\"schema_version\":\"okcanvas-service-client-token-registry-v1\",\"tokens\":[{\"token_id\":\"alice-web\",\"token_sha256\":\"<sha256>\",\"tenant_id\":\"tenant-a\",\"principal_id\":\"alice\",\"roles\":[\"agent-user\"]}]}"
```

The client sends the raw external token:

```http
Authorization: Bearer <raw external token>
```

Do not send `X-OKCanvas-Admin-Key` or `X-OKCanvas-Run-Submitter-Key` from a service client.

## Discover the contract

```http
GET /v1/service/capabilities
GET /v1/service/error-contract
GET /v1/service/whoami
```

Capabilities identify supported client families, attachment limits, durable SSE, current Skill
availability and whether Submission/Attachment features are configured.

## Agent and Session operations

```http
GET  /v1/service/agent-definitions
GET  /v1/service/agent-definitions/{agent_id}
POST /v1/service/sessions
GET  /v1/service/sessions
GET  /v1/service/sessions/{session_id}
POST /v1/service/sessions/{session_id}/clear
```

Session lists and details are principal-scoped.

## Attachment and Submission operations

```http
POST /v1/service/local-attachments
POST /v1/service/run-submissions/preflight
GET  /v1/service/run-submissions
GET  /v1/service/run-submissions/{submission_id}
POST /v1/service/run-submissions/{submission_id}/confirm
POST /v1/service/run-submissions/{submission_id}/prepare-approval
```

The existing bounded raw-body attachment upload and exact confirmation challenge remain unchanged.
Attachment slots and Sessions are checked for principal ownership before preflight.

## Approval operations

```http
GET  /v1/service/tool-approvals
GET  /v1/service/tool-approvals/{approval_id}/inbox
POST /v1/service/tool-approvals/{approval_id}/decision
```

Only `approval-operator` can use these routes. Approval scope is tenant-wide, allowing a separate
operator principal to decide a submitting user's Approval without granting access to that user's Run
or Session.

## Run, Event and Artifact operations

```http
GET  /v1/service/runs
GET  /v1/service/runs/{run_id}
GET  /v1/service/runs/{run_id}/outcome
POST /v1/service/runs/{run_id}/cancel
GET  /v1/service/runs/{run_id}/invocations
GET  /v1/service/runs/{run_id}/events
GET  /v1/service/runs/{run_id}/events/stream
GET  /v1/service/runs/{run_id}/artifacts
GET  /v1/service/runs/{run_id}/artifacts/{artifact_id}
```

Reconnect persisted SSE using either the `cursor` query or `Last-Event-ID`. Service clients must not
use `/v1/runs/{run_id}/sdk-stream`; that process-local stream remains a development surface.

## Client repositories

STEP069 creates contract placeholders only:

```text
agent-cli/
agent-web/
agent-desktop/
```

No final service client is implemented yet. The existing TUI and Node CLI remain test harnesses.
