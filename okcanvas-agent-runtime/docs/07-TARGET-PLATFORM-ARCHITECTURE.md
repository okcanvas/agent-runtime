# Target Platform Architecture

## Architectural position

`okcanvas-agent-runtime` begins as a modular monolith with explicit internal ports. It is not split into network microservices before workload, failure, and scaling evidence exists.

```text
CLI / future REST-SSE API / future Vue console
                    |
                    v
            Application services
  +-----------------+------------------+
  | Task & Run      | Approval         |
  | Definition      | Reference        |
  | Artifact        | Validation       |
  +-----------------+------------------+
                    |
                    v
             Execution coordinator
  +-----------------+------------------+
  | Agents SDK      | Tool dispatcher  |
  | Session adapter | Event normalizer |
  +-----------------+------------------+
                    |
       +------------+------------+
       |                         |
       v                         v
Optional integrations       Independent executors
Codex adapter               Validator
MCP adapters                future Windows worker
future PlanVM MCP
                    |
                    v
              Infrastructure
SQLite first / PostgreSQL later
append-only event journal
artifact filesystem first / object store later
workspace leases and hashes
```

## Product state versus SDK state

| State | Owner | Purpose |
|---|---|---|
| Task | OKCanvas product store | User or system work request and lifecycle. |
| Run | OKCanvas product store | One execution attempt against a Task. |
| Run Event | OKCanvas product store | Ordered canonical product event stream. |
| Approval | OKCanvas product store | Durable operator decision and execution claim. |
| Artifact | OKCanvas product store + artifact storage | Patch, report, event journal, validation output, RunState blob metadata. |
| Validation | OKCanvas product store | Independent machine result and counts. |
| Session | Agents SDK adapter | Conversation history only. |
| RunState | Agents SDK + encrypted/local artifact | Resume one interrupted Agent execution. |
| Trace | Agents SDK tracing | Diagnostics and latency/cost analysis. |
| Codex Thread | Codex adapter | Continuity inside the optional coding tool. |

No SDK object is the canonical product ledger.

## Initial runtime processes

The code remains one repository and one package, but may expose separate entrypoints:

1. **Control process** — CLI now, API later; creates tasks, reads state, records decisions.
2. **Execution worker** — runs Agent jobs and Tool calls. It can remain in-process at first.
3. **Validation process** — independent command contract; already proven for pytest.

Physical process separation is introduced only where it creates an actual safety or durability boundary.

## Target package map

The existing code is not immediately reorganized. New work converges on this map incrementally:

```text
src/okcanvas_agent_runtime/
  core/                 identifiers, clocks, hashes, shared errors
  catalog/              Agent, Tool, MCP and reference definitions
  tasks/                Task application service and repository port
  runs/                 Run, attempt and state transitions
  events/               canonical append-only events and subscribers
  approvals/            durable decisions, claims and resume policy
  artifacts/            metadata, SHA, retention and storage ports
  execution/            generic Agents SDK coordinator
  validation/           independent validators and results
  workspaces/           controlled copies, leases and integrity
  integrations/
    codex/               optional experimental adapter
    mcp/                 future read-only MCP adapters
    planvm/              future deterministic execution adapter
  persistence/          SQLite first, PostgreSQL adapter later
  interfaces/
    cli/
    api/                 future REST/SSE
```

Existing STEP001–STEP004 modules stay stable until the corresponding service extraction has tests. A broad file-move refactor is forbidden as a planning-only change.

## Deployment evolution

### Phase 1 — local modular monolith

- one Python installation;
- SQLite product store;
- filesystem artifact store;
- CLI entrypoints;
- controlled local worker execution.

### Phase 2 — server runtime

- FastAPI control surface;
- authenticated project ownership;
- SSE from persisted canonical events;
- worker process separated from API process;
- PostgreSQL and durable artifact storage.

### Phase 3 — integrations

- read-only MCP servers and clients;
- Windows validation worker;
- PlanVM MCP for approved deterministic plans;
- Codex external-project onboarding after project policy is proven.

Temporal or another durable workflow engine is considered only after concrete recovery requirements exceed the product store and worker lease model.
