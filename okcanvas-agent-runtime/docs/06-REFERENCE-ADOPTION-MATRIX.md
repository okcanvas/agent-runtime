# Reference Adoption Matrix

This document records what is adopted, wrapped, deferred, or explicitly rejected from the supplied reference source. It is based on inspected code, not README claims.

## Primary source: OpenAI Agents Python 0.19.0

| Reference capability | Inspected source | Decision | Product boundary |
|---|---|---|---|
| Agent and Runner loop | `src/agents/agent.py`, `src/agents/run.py` | ADOPTED in STEP007 | Declarative definitions configure the official Runner; no second model/tool loop exists. |
| Structured output | `src/agents/agent.py`, `src/agents/agent_output.py`, `src/agents/result.py` | ADOPTED in STEP007 | Definition schema must equal the registered runtime contract; final output is persisted as an Artifact. |
| Function Tools and approval | `src/agents/tool.py`, `src/agents/run_state.py` | Use through an adapter | SDK interruption state is execution state, not the approval ledger. |
| RunState serialization | `src/agents/run_state.py` | Use for paused Agent execution | Never treat it as the canonical Task or Run record. Persist SHA and schema/version metadata beside it. |
| Session protocol | `src/agents/memory/session.py` and implementations under `extensions/memory/` | Use later for conversation history | Session items are not Task, Run, Approval, Artifact, or Audit records. |
| Lifecycle hooks and streaming events | `src/agents/lifecycle.py`, `src/agents/stream_events.py`, `src/agents/run_internal/streaming.py` | RunHooks ADAPTED in STEP007; SDK stream classes REJECTED as STEP008 public contracts | Product canonical Events remain stable; SSE replays persisted `run_event` rows only. |
| Tracing | `src/agents/tracing/create.py`, `src/agents/tracing/processor_interface.py` | Trace linkage ADOPTED in STEP007; processor adapter DEFERRED | Trace ID is linked to Run state; Trace is observability, not immutable business Evidence. |
| MCP manager and transports | `src/agents/mcp/manager.py`, `src/agents/mcp/server.py`, `src/agents/mcp/util.py` | ADOPTED/ADAPTED in STEP009 | One allowlisted local stdio server, static Tool filter, bounded timeouts/retry, canonical redacted Tool Events. |
| Experimental Codex Tool | `src/agents/extensions/experimental/codex/` | Keep behind an optional adapter | Feature-gated, acceptance-tested, never the runtime core. |
| Sandbox Agent | `src/agents/sandbox/` | Defer | Codex already proved the coding slice. Do not create a second coding execution stack yet. |
| Realtime and voice | `src/agents/realtime/`, `src/agents/voice/` | Defer | Not required for the initial product. |
| Workspace path normalization | `src/agents/sandbox/workspace_paths.py` | Adapt in STEP006 | Resolve only POSIX relative paths under one manifest-declared root; reject traversal and drive-qualified paths. |
| Archive symlink/path safety | `src/agents/sandbox/session/archive_extraction.py` | Adapt in STEP006 | Reject symbolic-link components and unsafe path escape before serving reference content. |
| Bounded output policy | `src/agents/sandbox/util/token_truncation.py` | Adapt in STEP006 | Enforce hard search, file-byte and line-range limits; the catalog returns bounded exact lines rather than shell output. |

## Customer-service demo

Reference: `reference/upstream/openai-cs-agents-demo/`.

Adopt as ideas:

- explicit Agent definitions and handoff topology;
- UI separation between conversation, active Agent, context, and guardrail observations;
- typed frontend API contracts.

Do not adopt as product foundations:

- in-memory thread, attachment, and Agent state stores;
- unauthenticated Tool mutations;
- demo-only context as the canonical business state;
- UI components not connected to the actual backend event flow.

## Streaming API starter

Reference: `reference/upstream/openai-agents-streaming-api/`.

Adopt as an idea:

- a bounded FastAPI adapter and SSE transport.

STEP008 adapts this into local-admin-only endpoints over durable canonical Events rather than forwarding SDK stream objects.

Do not copy:

- direct exposure of SDK internals and instructions;
- unauthenticated session lookup/deletion;
- HTTP 200 for execution failure;
- wildcard CORS as an operating default;
- user input logging without redaction;
- session state presented as user authorization isolation.

## Temporal demo

Reference: `reference/upstream/temporal-openai-agents-demos/`.

Adopt as concepts only:

- long waits must not require an Agent process to stay alive;
- external work should be represented as retryable activities;
- human signals and workflow state need explicit durable contracts.

Defer Temporal itself until the local Task/Run/Approval model and failure modes are proven. PlanVM also remains a separate deterministic executor rather than the Agent runtime's planner.

## Mandatory reference-use workflow

For every STEP that touches a capability represented in `/reference`:

1. read `reference/CODE_MAP.md` and `reference/MANIFEST.json`;
2. inspect the smallest applicable upstream call path;
3. cite exact reference-relative files in the plan or implementation notes;
4. classify the result as adopted, adapted, deferred, or rejected;
5. validate that `reference/upstream/**` remained unchanged.

A STEP must not claim that no usable upstream mechanism exists unless the relevant reference path was inspected.

## Governing conclusion

The reference source is an answer key for implementation mechanisms. It is not a complete product architecture. The product must add durable work state, ownership, policy, canonical events, artifacts, independent validation, and operating interfaces around the SDK without reimplementing the SDK.

## Direct import prohibition

`/reference` is consulted as immutable implementation evidence only. Executable project code must use installed packages or product-owned adapters. `scripts/verify_no_reference_imports.py` rejects local reference namespace imports, reference-based `sys.path` manipulation, dynamic module loading, and path dependencies.

## STEP011 catalog API

- ADAPT `openai-cs-agents-demo/python-backend/server.py::_build_agents_list` into immutable, validated Agent-definition metadata endpoints.
- REJECT `openai-agents-streaming-api/src/api/utils/agent_router.py::get_agent_info` disclosure of instruction text, model/session internals and local configuration.
- Keep legacy Codex declaration folders separate from the canonical `definition.json` catalog rather than pretending the schemas are interchangeable.

## STEP012 — Recorded Run evaluation

See `docs/06-REFERENCE-ADOPTION-MATRIX-STEP012.md`. Structured final-output and Usage boundaries were adopted/adapted from the inspected SDK, while SDK `RunResult` persistence and direct `/reference` import were rejected.

## STEP012A — Windows SQLite handle release

- ADAPT explicit SQLite connection ownership and `close()` behavior from `openai-agents-python-0.19.0/src/agents/memory/sqlite_session.py`.
- Keep Evaluation persistence as product-owned state; do not import or repurpose SDK Session storage.
- Reject garbage collection, cleanup retries, or ignored `WinError 32` as substitutes for deterministic handle release.

## STEP013 — Evaluation Suite and explicit Baseline

| Reference | Decision | Use |
|---|---|---|
| `openai-agents-python-0.19.0/AGENTS.md` baseline review guidance | ADAPT | Compare against an explicit compatibility baseline, inspect the whole result set, and avoid treating passing local tests as sufficient evidence. |
| `openai-agents-python-0.19.0/src/agents/usage.py` | ADAPT | Aggregate additive token and request metrics across Suite members. |
| `openai-agents-python-0.19.0/examples/agent_patterns/llm_as_a_judge.py` | DEFER | Model judging is not authoritative and is outside STEP013. |
| `/reference` runtime import | REJECT | Runtime code uses project-owned Suite services and installed dependencies only. |


## STEP014 — Acceptance workspace lifecycle

| Reference | Decision | Use |
|---|---|---|
| `openai-agents-python-0.19.0/src/agents/sandbox/sandboxes/unix_local.py` | ADAPT | Distinguish runtime-owned temporary roots and release prerequisites before deletion. |
| `openai-agents-python-0.19.0/src/agents/mcp/manager.py` | ADAPT | Close resources in reverse order and remove lifecycle ownership in deterministic cleanup boundaries. |
| Best-effort cleanup that suppresses deletion errors | REJECT | Acceptance cleanup failure is preserved and reported, not counted as PASS. |
| `/reference` runtime import | REJECT | The implementation is project-owned and uses only the standard library. |

## STEP015 — Local operations console foundation

| Reference | Decision | Use |
|---|---|---|
| `openai-cs-agents-demo/ui/app/page.tsx` | ADAPT | Separate operating panels and derive display state from backend snapshots. |
| `openai-cs-agents-demo/ui/components/agent-panel.tsx` | ADAPT | Present Agent identity and capabilities without exposing instructions. |
| `openai-cs-agents-demo/ui/components/runner-output.tsx` | ADAPT | Present execution observations in a dedicated timeline/detail surface. |
| `openai-cs-agents-demo/ui/lib/api.ts` | ADAPT | Keep browser API access bounded in a small product-owned adapter. |
| `openai-cs-agents-demo/python-backend/main.py` permissive CORS and demo state | REJECT | The console is same-origin, local-admin-only, and reads durable product state. |
| ChatKit/Next.js source and dependency graph | DEFER | A build framework is not justified for the first read-only operating surface. |
| SDK raw stream objects in the UI | REJECT | The console displays persisted canonical Run Events only. |
| `/reference` runtime import | REJECT | Assets and services are product-owned and use installed dependencies only. |

## STEP016 — Operations console persisted live view

| Reference | Decision | Use |
|---|---|---|
| `openai-agents-streaming-api/src/api/utils/agent_router.py` | ADAPT | Keep a small SSE adapter and no-buffering response headers, but stream persisted product Events rather than SDK objects. |
| `openai-cs-agents-demo/python-backend/main.py` state stream | ADAPT | Explicitly own and close the browser connection lifecycle. |
| SDK `stream_events.py` and `run_internal/streaming.py` public exposure | REJECT | SDK events remain internal inputs to canonical Event normalization. |
| Native browser `EventSource` | REJECT | It cannot attach `X-OKCanvas-Admin-Key`; use same-origin authenticated GET fetch streaming. |
| In-memory listener queue as replay authority | REJECT | SQLite sequence and cursor are the replay authority. |
| `/reference` runtime import | REJECT | Browser and server adapters are product-owned. |

## STEP018 — Protected payload and governed read-only Run

| Reference | Decision | Use |
|---|---|---|
| `openai-agents-python-0.19.0/.agents/references/runstate-schema.md` | ADOPT | Keep SDK RunState as pause/resume execution state and keep secrets outside serialized context, Trace, and Tool output. |
| `openai-agents-python-0.19.0/src/agents/run_state.py` | ADAPT | Revalidate immutable SDK-facing identity before execution without using RunState as the Product request vault. |
| `openai-agents-python-0.19.0/src/agents/sandbox/entries/mounts/patterns.py` | ADAPT | Create sensitive product-owned files atomically with owner-only permissions where supported. |
| `openai-agents-python-0.19.0/src/agents/tracing/traces.py` | ADAPT | Keep secret material out of storage and expose only a non-secret key fingerprint. |
| SDK RunState or `/reference` as protected payload storage | REJECT | Protected payloads are AES-256-GCM product files outside SQLite and runtime imports use installed packages only. |


## STEP019 — Governed claim recovery and protected-payload retention

| Reference | Decision | Use |
|---|---|---|
| `openai-agents-python-0.19.0/src/agents/run_state.py` | ADOPT | Preserve the distinction between durable execution state, approval/resume identity, and Product-owned secrets. |
| `openai-agents-python-0.19.0/src/agents/result.py` | ADAPT | Apply terminal cleanup only after the owning execution boundary has reached a known result. |
| `openai-agents-python-0.19.0/src/agents/sandbox/session/base_sandbox_session.py` | ADAPT | Give temporary/sensitive resources an explicit lifecycle owner and observable cleanup result. |
| `openai-agents-python-0.19.0/src/agents/sandbox/session/sandbox_client.py` | ADAPT | Separate reconnect/recovery eligibility from destructive cleanup and require explicit local-operator action. |
| Raw execution claim token persistence | REJECT | SQLite stores only the active generation token SHA-256; the raw token exists only in the scheduling process memory. |
| Recovery of an already `RUNNING` Product Run | REJECT | STEP019 recovers only stale pre-start claims with Task `READY` and Run `CREATED`. |
| Automatic startup recovery and distributed worker lease | DEFER | Require a later measured multi-process design. |
| `/reference` runtime import | REJECT | Runtime code uses installed dependencies and product-owned implementations only. |

## STEP020 — Governed local Tool approval interruption and resume

| Reference area | Decision | Product use |
|---|---|---|
| `src/agents/tool.py` Function Tool `needs_approval` | ADOPT | The controlled `local_text_metrics` Tool always interrupts before execution. |
| `src/agents/result.py::to_state()` | ADOPT | The interrupted SDK result is converted to the authoritative SDK RunState. |
| `src/agents/run_state.py::to_json/from_json/approve/reject` | ADOPT | RunState is serialized, encrypted, restored in another process, and explicitly approved or rejected. |
| RunState context for raw request storage | REJECT | Context contains only an opaque execution ID; the raw request remains in the product-owned encrypted payload store. |
| Plain RunState JSON in SQLite or Events | REJECT | RunState is AES-256-GCM encrypted outside SQLite. |
| General arbitrary local Tool approval | DEFER | STEP020 allows exactly one controlled read-only Tool. |

## STEP021 — Read-only local approval inbox

| Reference area | Decision | Product use |
|---|---|---|
| `examples/tools/shell_human_in_the_loop.py` pending interruption loop | ADAPT | Present pending approvals as explicit durable records rather than hidden execution state. |
| `examples/sandbox/extensions/temporal/temporal_sandbox_tui.py` approval status surface | ADAPT | Separate approval observation from the running execution timeline. |
| Approval controls in the general Operations Console | REJECT | STEP021 is observation-only; decision authority is not introduced into the read console. |
| Raw interruption arguments and RunState storage metadata | REJECT | Inbox responses expose bounded product metadata only. |
| `/reference` runtime import | REJECT | Runtime uses installed packages and product-owned stores and adapters. |

## STEP022 — Windows live-acceptance closure harness

| Reference area | Decision | Product use |
|---|---|---|
| `examples/tools/shell_human_in_the_loop.py` explicit interruption loop | ADAPT | A closure result is accepted only after explicit approve and reject branch outcomes are available. |
| `examples/sandbox/extensions/temporal/temporal_sandbox_tui.py` separation of approval and execution state | ADAPT | STEP021 observation and STEP020 decision execution remain separate child acceptances. |
| General Operations Console decision controls | REJECT | STEP022 is operational validation only and adds no product mutation surface. |
| Child raw output aggregation into the compact summary | REJECT | The summary carries only safe state, cleanup, exit, and failed-check metadata. |
| `/reference` runtime import | REJECT | Runtime and scripts use installed dependencies and project-owned code only. |

## STEP023 — Minimal local approval operator CLI

| Reference area | Decision | Product use |
|---|---|---|
| `examples/tools/shell_human_in_the_loop.py` explicit decision prompt | ADAPT | Require one explicit approve or reject confirmation per pending interruption. |
| `examples/sandbox/extensions/temporal/temporal_sandbox_tui.py` separate approval controls | ADAPT | Keep observation in the read-only console and decisions in a separate local CLI. |
| `always_approve` / `always_reject` | REJECT | STEP023 permits one approval per command only. |
| Remote operator Control API | REJECT | Authority keys may be sent only to an explicit loopback URL. |
| Browser decision controls | DEFER | Not justified while the bounded CLI is adequate. |
| `/reference` runtime import | REJECT | Runtime uses installed packages and product-owned code only. |


## STEP024 — Store replenishment review Agent

| Reference area | Decision | Product use |
|---|---|---|
| `openai-agents-python-0.19.0/examples/tools/programmatic_tool_calling.py` inventory/demand example | ADAPT | Reuse the explicit inventory, forecast, inbound, safety-stock equation as a bounded business calculation contract, without adding programmatic Tool execution. |
| `openai-agents-python-0.19.0/examples/financial_research_agent/agents/risk_agent.py` | ADAPT | Use one focused business specialist with a Pydantic structured output rather than a general chat Agent. |
| `openai-cs-agents-demo/python-backend/airline/agents.py` specialist boundaries | ADAPT | Give the Agent one narrow business responsibility and explicit missing-data behavior. |
| Autonomous business writes, Handoffs, and external Tool chains from the demos | REJECT | STEP024 is read-only and analyzes only the supplied immutable snapshot. |
| `/reference` runtime import | REJECT | Runtime uses installed packages and project-owned contracts only. |

## STEP024A — Live business output diagnostics and round-trip validation

| Reference area | Decision | Product use |
|---|---|---|
| `openai-agents-python-0.19.0/src/agents/agent_output.py::AgentOutputSchema.validate_json` | ADOPT | Treat the configured output type and Pydantic JSON validation as the SDK output authority. |
| Product-side contract-specific `TypeAdapter` JSON round trip | ADAPT | Independently verify serializability and the complete business contract before Artifact persistence. |
| Acceptance placeholder `{}` when Artifact count is not exactly one | REJECT | Preserve the terminal Run, HTTP outcome, Artifact count, and original validation failure instead of manufacturing a misleading object. |
| `/reference` runtime import | REJECT | Runtime uses installed dependencies and project-owned output registry code only. |


## STEP024B — Deterministic business output recovery

| Reference area | Decision | Product use |
|---|---|---|
| `openai-agents-python-0.19.0/src/agents/run_error_handlers.py` | ADOPT | Use the official `invalid_final_output` handler boundary rather than catching arbitrary SDK exceptions. |
| `openai-agents-python-0.19.0/tests/test_invalid_final_output_handler.py` | ADAPT | Return a contract-valid deterministic fallback and verify the SDK accepts it as final output. |
| Retrying the model for arithmetic correction | REJECT | Replenishment arithmetic is deterministic and must not consume another model turn. |
| Generic fallback for every Agent | REJECT | Recovery is restricted to the store replenishment contract. |
| `/reference` runtime import | REJECT | Runtime uses the installed SDK and project-owned deterministic calculator. |


## STEP025 — Governed read-only commerce snapshot ingress

| Reference area | Decision | Product use |
|---|---|---|
| `openai-agents-python-0.19.0/src/agents/mcp/server.py` | INSPECT / REJECT FOR SOURCE ACQUISITION | The SDK MCP server is a Runner-internal model Tool boundary, so it cannot establish the protected business source before confirmation. |
| `openai-agents-python-0.19.0/tests/mcp/test_runner_calls_mcp.py` | INSPECT | Confirms MCP calls occur while Runner executes model-selected tools. |
| Hardened HTTP client behavior (`follow_redirects=False`, explicit timeout) | ADAPT | Product-owned preflight ingress disables redirects, environment proxy trust, and retries. |
| Model-driven ERP MCP Tool as inventory source of truth | REJECT | Confirmation, deterministic recovery, Artifact, and Evaluation must bind the complete pre-execution snapshot. |
| Remote hosts, arbitrary endpoints, source writes, and credential persistence | REJECT | STEP025 allows one loopback GET adapter with environment-only bearer injection. |
| `/reference` runtime import | REJECT | Runtime uses installed dependencies and product-owned ingress code only. |
