# OKCanvas Agent Platform



**OKCanvas Agent Platform** is an evidence-first runtime and integration workspace for building governed, persistent AI agents around the OpenAI Agents SDK, MCP connectors, durable execution state, approvals, sessions, artifacts, and evaluations.

The project focuses on a practical question: **how do you turn an LLM-powered agent into an application runtime that can be inspected, resumed, governed, and integrated with real business systems?**

> **Project status:** development preview. The local SQLite/filesystem topology is the default. PostgreSQL-backed metadata has been exercised against a real PostgreSQL server. S3-compatible Artifact storage composition is implemented, while the current external Object Storage live gate is intentionally pending until a MinIO/S3 test environment is available. The repository is not yet presented as production-ready.

## Highlights

* **Generic Agent runtime** built on the OpenAI Agents SDK with declarative Agent definitions and model routing.
* **MCP integration** with independently packaged read-only Groupware and Organization Context connectors.
* **Sub-agents and delegation** through Agent-as-Tool and handoff boundaries.
* **Governed execution** with durable Run submissions, persisted events, explicit Tool Approval, cancellation, and resumable state.
* **Persistent Sessions** with encrypted local model conversation history and independently persisted Session lifecycle metadata.
* **Artifact lifecycle** with metadata/binary separation, integrity checks, local filesystem storage, and an optional S3-compatible object-storage adapter.
* **Evaluation support** for recorded Runs, evaluation suites, and baselines.
* **Streaming** through persisted events and SSE.
* **Read-only sandbox/workspace boundaries** for controlled project inspection.
* **Product-facing Service API and CLI** separated from direct Runtime source imports.
* **Evidence-first validation** with deterministic acceptance runners, architecture checks, manifests, and opt-in live gates.

## Architecture

```text
                        +----------------------+
                        |   Product clients    |
                        | CLI / future Web UI  |
                        +----------+-----------+
                                   |
                         HTTP / SSE|  Service API
                                   v
+------------------+     +---------+----------+      +-------------------+
| Local operator   |---->| OKCanvas Agent     |----->| OpenAI Agents SDK |
| / Control client |     | Runtime            |      +-------------------+
+------------------+     |                    |
                         | routing            |-----> MCP connectors
                         | sessions           |       - Groupware
                         | runs / events      |       - Org Context
                         | approvals          |
                         | artifacts          |-----> Local FS / S3-compatible
                         | evaluations        |
                         +---------+----------+
                                   |
                                   +---------> SQLite (default)
                                   |
                                   +---------> PostgreSQL hybrid metadata
```

The workspace keeps Runtime, Product CLI, Connectors, and Connector Examples as **independent projects**. Cross-project implementation imports are intentionally forbidden; integration happens through declared HTTP, SSE, MCP, and external-system contracts.

## Repository layout

| Path                                                   | Purpose                                                                                                                       |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| `okcanvas-agent-runtime/`                              | Core Python Agent runtime, APIs, persistence adapters, Sessions, approvals, Artifacts, evaluation, MCP and sandbox boundaries |
| `okcanvas-agent-cli/`                                  | Product-facing Node.js Service API CLI                                                                                        |
| `okcanvas-connectors/groupware-mcp-server/`            | Read-only Groupware MCP connector                                                                                             |
| `okcanvas-connectors/organization-context-mcp-server/` | Read-only Organization Context MCP connector                                                                                  |
| `okcanvas-connector-examples/`                         | Deterministic fake external systems used for development and acceptance                                                       |
| `specs/`                                               | Machine-readable workspace and distribution contracts                                                                         |
| `docs/`                                                | Architecture plans, audits, issues, handoff records, and validation evidence                                                  |
| `scripts/`                                             | Workspace-level validation, packaging, and acceptance tooling                                                                 |

## Quick start on Windows

### Requirements

* Windows 10/11
* Python 3.10+
* Node.js 22+
* An OpenAI API key

Optional integrations require their own local or external environment:

* Docker for sandbox live execution
* PostgreSQL for `postgresql-hybrid-v1`
* MinIO, Amazon S3, or another S3-compatible service for `object-storage-artifact-v1`

### 1. Set up the workspace

From the repository root:

```bat
sh_setup_workspace.cmd
```

Each subproject keeps its own Python virtual environment or Node.js dependency graph.

### 2. Create the local Runtime environment

```bat
cd okcanvas-agent-runtime
sh_init_local_env.cmd
```

This creates `.env.local` from the canonical template and generates distinct local authority/encryption keys. Then set at least:

```text
OPENAI_API_KEY=<your-key>
OKCANVAS_AGENT_MODEL=<model-id>
```

Do not commit `.env.local` or credential values.

### 3. Start the Runtime API

```bat
sh_run_api.cmd
```

The default Control API binds to:

```text
http://127.0.0.1:8765
```

### 4. Open the local governed terminal client

In another terminal:

```bat
cd okcanvas-agent-runtime
sh_tui.cmd
```

The local client reads the canonical `.env.local`, connects only to a loopback Control API, and uses the Runtime-owned submission, approval, Session, Run, Event, Artifact, and evaluation flow.

## Persistence

The default configuration is intentionally local and explicit:

```text
Product metadata     SQLite
Session history      Encrypted local SQLite
Artifact binary      Local filesystem
```

An opt-in PostgreSQL topology is also implemented:

```text
OKCANVAS_PRODUCT_STORE_BACKEND=postgresql-hybrid-v1
OKCANVAS_POSTGRESQL_DSN=postgresql://...
```

Install the optional driver first:

```bat
.venv\Scripts\python.exe -m pip install -e ".[postgresql]"
```

In this topology, Product/Run/Submission/Approval/Evaluation/Session lifecycle metadata can use PostgreSQL while actual SDK conversation history remains in encrypted local SQLite.

## S3-compatible Artifact storage

Local filesystem Artifact storage remains the default. To use the optional S3-compatible adapter, install:

```bat
.venv\Scripts\python.exe -m pip install -e ".[object-storage]"
```

Then configure the deployment-specific values described in `okcanvas-agent-runtime/.env.local.example`, including an existing bucket, prefix, endpoint/region when required, and the standard boto3/AWS credential chain.

The current repository includes the S3-compatible composition and isolated-prefix live acceptance gate. **External MinIO/S3 live acceptance for the current build is still pending.**

## Security model

The current runtime deliberately favors explicit boundaries over convenience:

* local administrator and Run-submitter authorities are distinct;
* the Control API binds to loopback by default;
* Tool writes require explicit approval flows where supported;
* production Connectors in this workspace are read-only;
* Session history is encrypted at rest in the local Session store;
* Service API clients authenticate with bearer tokens represented by SHA-256 registry entries;
* secret values are excluded from packaged validation evidence;
* external storage credentials are delegated to the standard SDK credential chain rather than persisted by the Artifact store.

**Important:** the current Admin and Service routes still share one FastAPI application/listener. Do not expose the combined listener directly to an untrusted network. Physical Admin/Service listener isolation is an identified pre-production boundary.

## What is not implemented yet

The repository intentionally does not claim the following as complete:

* physical Admin API / external Service API listener separation;
* versioned production PostgreSQL migration and rollback lifecycle;
* dependency-aware readiness endpoints for all external dependencies;
* dynamic Service token expiry/revocation/rotation;
* Artifact orphan inventory, quarantine, and garbage collection;
* distributed Session history / multi-node HA;
* physical Worker separation with heartbeat and lease renewal;
* governed Groupware write execution;
* durable Automation scheduler/registry;
* current-build MinIO/S3 live acceptance.

These boundaries are tracked explicitly rather than represented as completed functionality.

## Validation philosophy

OKCanvas uses an evidence-first development model:

1. inspect the actual implementation and contracts;
2. reproduce and record failures instead of hiding them;
3. keep deterministic tests separate from optional live-system tests;
4. verify package manifests and fresh extraction behavior;
5. avoid promoting capabilities that have not been exercised in the environment they depend on.

Internal validation and continuation records live under `docs/`, `HANDOFF.md`, and `PLANS.md`.

## Development notes

* The repository currently uses Windows `.cmd` launchers as the primary accepted workspace entrypoints.
* Connector examples are deterministic development fixtures; they are not production dependencies.
* Direct legacy/Codex execution surfaces remain explicit developer-oriented boundaries and are not the Product Service API contract.
* The public-facing Product CLI communicates only through authenticated Service HTTP/SSE contracts.

## License

This repository snapshot does **not** currently include an open-source license. Public source visibility does not grant reuse, modification, or redistribution rights by itself. Add an explicit `LICENSE` file before publishing the project under an open-source license.

<details>
<summary>Build identity</summary>

```text
Current Workspace: WORKSPACE_STEP008R4R7A1_GIT_REPOSITORY_HYGIENE_AND_RETAINED_RUNTIME_DIST_TRACKING
Workspace Version: 0.8.4-r7a1
Current Runtime: STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE
Runtime Version: 2.75.0
State: IMPLEMENTED_STATIC_VALIDATED_TEST_EXECUTION_DEFERRED_BY_USER_MINIO_PENDING
Promotion: NOT_READY
```

The long-form build identity is retained for deterministic package handoff and current-document SOT validation. It is not intended as the public product name.

</details>
