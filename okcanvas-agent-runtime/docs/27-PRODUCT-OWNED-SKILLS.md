# Product-owned Skill API and usage

## Service discovery

Authenticated service clients discover Skill support through:

```http
GET /v1/service/capabilities
GET /v1/service/skills
GET /v1/service/skills/{skill_id}
```

The response exposes immutable metadata, allowed Agent IDs, required capabilities, resource hashes,
and package SHA-256. It does not expose the Skill instructions or resource contents.

## Running a Skill-enabled Agent

A client does not execute a Skill directly. It selects an Agent definition that explicitly binds the
Skill. The first Skill-enabled Agent is:

```text
skill-document-review-agent
  input mode: local-attachment-v1
  Skill: document-review-v1
  output: LocalDocumentReviewResult
```

The normal service flow remains unchanged:

1. upload one bounded PDF, PNG, or JPEG through `POST /v1/service/local-attachments`;
2. submit `skill-document-review-agent` and the returned attachment ID through
   `POST /v1/service/run-submissions/preflight`;
3. exactly confirm and schedule through the existing governed Submission API;
4. consume persisted SSE and verified Artifacts.

The server resolves and verifies the Skill package, composes effective instructions, decrypts the
attachment only at schedule time, and runs the installed SDK. The client never receives Skill
filesystem paths or server secrets.

## Integrity behavior

A submission is Runtime-bound to the exact Skill package and implementation hashes. Editing the
manifest, instructions, resources, Agent binding, or Skill Runtime after preflight changes the
Runtime binding and prevents execution under the old confirmation.

## Not supported in V1

Clients cannot upload, edit, install, enable, disable, or execute Skill packages. There is no Skill
marketplace, Shell Skill, user code, dynamic dependency installation, or model-selected Skill.
