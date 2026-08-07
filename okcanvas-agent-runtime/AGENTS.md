# AGENTS.md — Project Constitution

## 1. Evidence before claims

1. Never guess about code, configuration, behavior, versions, or execution results.
2. Inspect the actual file and relevant call path before reaching a conclusion.
3. Separate confirmed facts, code-derived inferences, and unverified hypotheses.
4. Never claim that a build, test, server, model call, browser flow, or integration succeeded unless it was actually executed and its evidence was retained.
5. A zero-test run is not acceptance evidence.

## 2. Change discipline

1. Read `HANDOFF.md` and the current plan under `docs/plans/` before editing.
2. Determine the affected files and contracts before changing code.
3. Keep changes within the active STEP scope.
4. Review the final diff for unrelated modifications.
5. Do not modify generated or external reference source merely to make local checks pass.

## 3. Reference constitution

1. `reference/upstream/**` is an immutable source-of-truth snapshot of external projects supplied for study.
2. Actively consult `/reference` while planning, implementing, reviewing, and validating relevant work. It is an implementation answer key, not passive archive material.
3. Before introducing or reimplementing Agent SDK, RunState, Session, MCP, tracing, streaming, Codex integration, workflow, or Agent UI mechanisms, inspect the applicable reference code first.
4. Record what was adopted, adapted, deferred, or deliberately rejected, with exact repository-relative reference paths.
5. Never edit, format, patch, vendor-import, or execute local application code from `reference/upstream/**` as though it were our implementation.
6. Never import executable application code from `/reference`; use installed dependencies and product-owned adapters only.
7. Inspect `reference/CODE_MAP.md` and `reference/MANIFEST.json` before recursively searching reference source.
8. Reference findings must distinguish upstream behavior from our design and implementation.
9. Preserve each upstream `LICENSE` file.
10. Run `python scripts/verify_reference.py` after any packaging or filesystem operation that may affect references.

## 4. Namespace constitution

1. `specs/agents/`, `specs/mcp/`, and `specs/tools/` contain declarative definitions, policies, contracts, and evaluation assets.
2. These specification directories are not Python packages and must not contain `__init__.py`.
3. All executable Python code belongs below `src/okcanvas_agent_runtime/`.
4. Never create root Python packages named `agents` or `mcp`; those names belong to upstream SDKs.
5. Never manipulate `sys.path` to import code from `reference/upstream/`.

## 5. Safety boundaries

1. No real database SQL execution, DDL, DML, EXPLAIN, or legacy SQL execution is allowed unless a future constitution explicitly changes this.
2. No production or external-system write is allowed.
3. Shell, Git write, network, secret access, and workspace mutation require explicit tool policy and acceptance coverage before enablement.
4. A Codex subprocess must not inherit the complete parent environment; use an explicit allowlist.
5. STEP002 Codex workspaces must be controlled Git repositories, contain no symbolic links, and keep Evidence outside the workspace.
6. STEP003 write is allowed only in a disposable clean Git copy with an exact existing-file allowlist. New, staged, deleted, renamed, binary, committed, web-search, MCP, and out-of-allowlist changes fail closed.
7. Independent validators outside Codex are authoritative for build/test success. Codex statements are not validation evidence.
8. STEP004 approval state and RunState files must remain outside the workspace, be written atomically, and be integrity-checked before resume.
9. Approval is whole-run only. Do not claim per-command Codex approval. A terminal approval record must reject replay.
10. Model statements are not evidence. Exit codes, test reports, hashes, immutable artifacts, and verified state are evidence.
11. Approval decisions require both local-admin and Run-submitter authority plus the exact decision confirmation. Local operator clients must refuse non-loopback Control API URLs.
12. The general Operations Console remains read-only; approval decisions use a separately reviewed operator surface.

## 6. STEP completion

A STEP may be marked complete only when:

- its stated acceptance criteria are met;
- commands actually executed are listed in `HANDOFF.md`;
- unexecuted checks are listed explicitly;
- known limitations and next work are recorded;
- source ZIP and SHA-256 are produced when the STEP changes the distributable repository.

## Local live-acceptance evidence

- `docs/evidence/step002-live/**`, `docs/evidence/step003-live/**`, `docs/evidence/step004-live/**`, `docs/evidence/step007-live/**`, and `docs/evidence/step008-live/**` are local operational evidence and must not be committed or packaged into a source handoff ZIP.
- `.env.local.cmd` may contain secrets and must never be committed, packaged, printed, or copied into Evidence.
- A live-acceptance invocation must use its own unique directory and must never reuse another invocation's thread state.
- STEP003 workspace-write is live accepted only for the controlled fixture and remains disabled for external projects.
- STEP004 persisted approval state may contain the raw local task request and is sensitive operational state; never package or commit it.
- STEP003 core acceptance and disposable cleanup are separate evidence domains. Cleanup failure must not erase successful core checks, but STEP003 completion still requires a later run with cleanup state `COMPLETED`.

- Local environment files are configuration data. Project launchers must never `call`, source, or execute them.

## 7. Active product direction after STEP031

1. The active development center is the reusable Agent Runtime, not continued replenishment-domain expansion.
2. Existing business vertical slices are evidence that Runtime boundaries work; they must not leak business contract names or business algorithms into generic gateway code.
3. Add a new business rule only when it is required to prove or protect a reusable Runtime contract.
4. Runtime registries must be explicit, closed, product-owned compositions. Do not dynamically import arbitrary Python from Agent specifications.
5. Contract-specific recovery remains opt-in. Absence of a registered recovery means the SDK failure propagates; never install a universal fallback.
6. Executable Runtime behavior covered by exact confirmation must be represented by a deterministic product-owned binding SHA.
7. A Runtime binding mismatch after preflight requires a new preflight and confirmation and must fail before Product or approval state.
8. Never silently migrate a pending submission whose original Runtime binding cannot be proven.

## 8. Process-loss reconciliation constitution after STEP034

1. Never automatically re-run a governed model execution merely because the hosting process disappeared.
2. A previous-process `EXECUTION_STARTED/RUNNING` record may be reconciled only through an explicit authenticated local-operator action.
3. Reconciliation must terminalize the same Product Task and Run; it must not create a replacement execution.
4. Candidate identity requires a different persisted process owner, exact RUNNING Product state, and no registered Artifact.
5. The old claim generation must be invalidated before any late previous-process state can be accepted.
6. Active lifecycle Events, token metadata, and Artifact registration must fail on a terminal Run.
7. Failed process-loss payloads follow the existing investigation retention policy; they are not deleted as successful output.
8. STEP034 does not claim SDK resume, external-call cancellation, distributed leasing, or cross-process exactly-once execution.

## 9. Terminal outcome reconciliation constitution after STEP035

1. A terminal Product Task/Run is authoritative and must never be re-executed merely because the governed completion observer did not finish.
2. Reconciliation is explicit, authenticated, local-operator controlled, and requires a previous process or a provably partial terminalization.
3. `SUCCEEDED` deletes its protected payload immediately; `FAILED` and `CANCELLED` retain theirs for the configured investigation window.
4. Reconciliation preserves the same Task, Run, terminal Event, and successful Artifact and creates no Evaluation.
5. Exactly one `payload.retention.applied` Event may exist per Run for this lifecycle outcome.
6. Repeated reconciliation is a no-op.
7. Automatic startup mutation, SDK resume, model retry, replacement executions, and distributed leases remain prohibited.

## 10. Recorded Evaluation Runtime-binding constitution after STEP036

1. Recorded-Run Evaluation must verify the exact executable Runtime binding recorded by `agent.definition.resolved`.
2. Agent definition verification alone is insufficient; Output Runtime, SDK version, MCP definition/module, local Tool policy/implementation, and execution engine are part of the trust boundary.
3. A missing, malformed, tampered, or currently unverifiable Runtime binding fails closed as `RUNTIME_BINDING_DRIFT` and creates no Evaluation result.
4. Pre-STEP033 Runs without binding evidence must not be guessed, backfilled, or silently declared comparable.
5. The verified Runtime binding SHA must be persisted with each new Evaluation and exposed as non-secret evidence.
6. Recorded Evaluation remains offline from Agent execution: no model, MCP, Tool, SDK Runner, retry, resume, or replacement Run is allowed.
7. Historical executable Runtime loading and dynamic plugin import remain prohibited unless a future separately governed design changes this.

## 11. Reference-wide walking-skeleton constitution after STEP036A

1. The next executable Runtime sequence is governed by `docs/plans/STEP036A_REFERENCE_WIDE_RUNTIME_CAPABILITY_MASTER_PLAN.md`.
2. Build the P0 capability skeleton before resuming open-ended depth-first hardening.
3. Every new capability must use the actual installed SDK primitive identified by the reference audit; do not invent a parallel abstraction that bypasses the SDK.
4. Routing means governed native Handoff in the first slice. Parallelization is application orchestration and is not a native Router/Runner feature.
5. Generic Function Tool support precedes Agent-as-Tool because `Agent.as_tool()` is implemented on the Tool substrate.
6. SDK streaming precedes visible Handoff and nested-Agent UX. Ephemeral model deltas and persisted Product Events remain separate data classes.
7. Introduce SQLite Session alone before combining Session with Handoff, approval, compaction, or external backends.
8. The read-only Operations Console stays read-only. Interactive run submission is a separate run-submitter surface; approval decisions remain a separate operator surface.
9. Do not declare the basic Agent Runtime skeleton complete until the integrated STEP045 acceptance demonstrates Tool-free, Tool, approval, MCP, streaming, Handoff, Agent-as-Tool, Session, Guardrail, Artifact, and Evaluation flows.
10. Sandbox, Temporal, realtime, voice, remote Session backends, and broad hosted Tool support are independent later tracks, not P0 prerequisites.

## 12. Sub-Agent invocation and workspace isolation constitution after STEP036B

1. Every sub-Agent is an independently versioned definition under `specs/agents/<agent-id>`; anonymous model-generated Agent definitions are prohibited.
2. Every root, Handoff, and Agent-as-Tool execution has a distinct invocation ID and state namespace.
3. Handoff and Agent-as-Tool do not imply filesystem isolation; the product Runtime must create it explicitly.
4. `workspace_access=none` is the default. A language-only Agent receives no physical workspace and no filesystem capability.
5. Every file-capable invocation receives a separate Runtime-generated workspace or Sandbox session. Parent and child Agents must not share a writable root by default.
6. Parent/child transfer is limited to typed input, filtered history, immutable snapshots or read-only mounts, Artifact references, and bounded structured results.
7. Prompt text, model output, Tool arguments, and Agent display names must never select a host workspace root or mount.
8. Workspace policy, provider, materialization, grants, cleanup/export implementation, child definition closure, and nesting limits are part of the Runtime binding.
9. Session history, protected payload storage, workspace state, and long-term memory are distinct lifecycles and must not be conflated.
10. Separate host folders prevent accidental collision but are not sufficient hostile-code containment; arbitrary code requires a real governed isolation provider.
11. Process-loss handling must never auto-resume or re-run a child Sandbox or model execution without a separately governed design.
12. `docs/plans/STEP036B_SUB_AGENT_INVOCATION_AND_WORKSPACE_ISOLATION.md` is binding for STEP040 and later sub-Agent/file-capability work.


## 13. Interactive Runner constitution after STEP037

1. `/runner` is a separate governed Run-submitter surface; it is not an extension of the read-only Operations Console.
2. Interactive execution must use the existing preflight, encrypted protected payload, exact confirmation, Product Task/Run, canonical Event, Artifact, and Evaluation services. No browser-only execution path or second ledger is allowed.
3. The Runner requires distinct local-admin and Run-submitter authorities. Keys may be retained only in current-tab `sessionStorage`; raw request and model output must not be stored there.
4. The Runner must never call the direct `POST /v1/runs` endpoint.
5. Local Tool approval preparation may be exposed, but approval and rejection decisions remain in the separate Approval Operator surface.
6. The Operations Console remains GET-only and read-only.
7. Browser display of final output must use a verified Artifact API that exposes no host filesystem path.
8. Persisted canonical Event SSE is not native SDK streaming. Raw model and Tool deltas remain a separate STEP039 concern.
9. The Runner must not imply support for Handoff, Agent-as-Tool, Session, Guardrail, or parallel execution before their individual Runtime contracts are implemented.
10. Any future Runner feature must preserve the sub-Agent invocation and workspace-isolation constitution.


## 14. Generic Function Tool Runtime constitution for STEP038

1. `docs/plans/STEP037A_GENERIC_FUNCTION_TOOL_RUNTIME_IMPLEMENTATION_PLAN.md` is binding for STEP038.
2. Executable Function Tools resolve only through a closed product-owned Registry; Tool specifications may never select or import arbitrary Python modules.
3. Every local Function Tool has an immutable definition, policy, exact input/output schemas, Runtime version, implementation identity, and approval mode under `specs/tools/<tool-id>`.
4. Use the installed SDK `FunctionTool`/`function_tool`, strict JSON schema, `ToolContext`, native `needs_approval`, and RunState interruption/resume. Do not build a parallel Tool or approval engine.
5. Tool definition, policy, schemas, implementation, approval mode, SDK kind/options, and execution engine are part of the confirmation-bound Runtime binding.
6. Generic lifecycle policy must distinguish registered local Function Tools from allowlisted MCP Tools and fail closed on every other Tool origin.
7. Raw Tool arguments, raw Tool results, protected payload, secrets, and implementation tracebacks are not canonical Event payloads.
8. STEP038 V1 proves one read-only non-approval Function Tool and the existing approval-required `local_text_metrics` Tool through the same Registry.
9. Mixed MCP/Function Tool Agents, mixed approval modes in one Agent, multiple approval interruptions, Shell/hosted Tools, Tool Search, programmatic Tool calling, and Tool Guardrails are deferred.
10. The Interactive Runner may display Tool mode and approval-required state but must never approve or reject; decisions remain in the Approval Operator.
11. Existing pending Tool submissions whose prior Runtime binding cannot be proven after migration must be recreated and exactly reconfirmed.
12. STEP038 executable work is prohibited until STEP037 Windows acceptance passes all 24 checks.

## 15. Generic Function Tool Runtime constitution after STEP038

1. All local Function Tools must resolve through the closed product-owned `FunctionToolRuntimeCatalog`; Agent definitions, prompts, model output, and Tool arguments may not select Python factories or implementation modules.
2. Every Tool must have an immutable directory under `specs/tools/<tool-id>/` containing definition, policy, strict input schema, strict output schema, and documentation.
3. Tool definition, policy, both schemas, implementation, SDK kind, approval mode, and selected execution engine are Runtime-bound. Any drift requires a new preflight and exact confirmation.
4. P0 permits exactly one registered local Function Tool per Agent and forbids MCP/Function Tool mixing and mixed approval modes.
5. `approval_mode=NEVER` uses the normal governed confirmation/scheduler path. `approval_mode=ALWAYS` uses native SDK interruption/RunState and the separate Approval Operator.
6. Raw Tool arguments, protected source text, Tool call IDs, and raw Tool results must not be persisted in canonical Product Events. Safe identity/presence metadata only is allowed.
7. A rejected Tool executes zero times; an approved Tool executes exactly once; repeated decisions are idempotent replays.
8. Interactive Runner may prepare an approval but may not decide it.
9. Shell, network, filesystem, hosted Tools, dynamic Tool Search/plugins, multiple interruptions, Handoff, Agent-as-Tool, Session, and Tool Guardrails remain outside STEP038.
10. Every future STEP must update executable code and the ZIP-contained plan/handoff/evidence together so another conversation can resume from the ZIP alone.

## 16. Native SDK streaming constitution after STEP039

1. Native SDK streaming means actual installed-SDK `Runner.run_streamed()` plus `result.stream_events()`; persisted Product Event SSE is not native streaming.
2. The Product execution task owns and fully consumes the SDK stream. An HTTP subscriber never owns the SDK iterator and disconnect must not cancel or rerun execution.
3. Native stream data is bounded, process-local, ephemeral, authenticated, and explicitly labeled non-durable. It must not be inserted into the canonical Product Event ledger.
4. Only output text delta, safe Run-item type/name metadata, Agent display-name changes, and stream lifecycle metadata are exposed in V1.
5. Function-call argument delta, Tool arguments/results, reasoning content, prompts, instructions, secrets, and raw SDK objects are prohibited from the stream adapter.
6. Canonical lifecycle hooks and Product Events remain authoritative for audit, recovery, Artifact, retention, and Evaluation.
7. Native stream adapter and broker implementation are part of the generic execution Runtime binding; drift requires a new preflight and exact confirmation.
8. A process restart may make an ephemeral stream unavailable. The API must fail honestly and must not synthesize native deltas from persisted Events.
9. Approval-interrupted RunState streaming, Handoff streaming, nested-Agent streaming, Session streaming, and Guardrail streaming are deferred to their owning Runtime steps.
10. STEP040 must establish invocation identity before STEP041 Handoff and STEP042 Agent-as-Tool.

## 17. Sub-Agent invocation-scope constitution after STEP040

1. Every Product Run has exactly one product-owned `ROOT` Agent invocation. Native SDK objects and display names are not invocation identity.
2. Every future Handoff and Agent-as-Tool execution must create a distinct child invocation before the child model, Tool, MCP, or nested Runner is allowed to execute.
3. Child Agent destinations resolve only from the immutable parent definition's declared `handoffs` or `agent_tools`; prompts, model output, Tool arguments, and API callers may not choose undeclared Agent definitions.
4. Root and child invocations must preserve exact `run_id`, `root_invocation_id`, `parent_invocation_id`, kind, depth, ordinal, state namespace, Agent-definition SHA, and Runtime-binding SHA.
5. Child graph closure, maximum depth, Handoff count, Agent-as-Tool count, workspace policy, and invocation-scope implementation are confirmation-bound Runtime state.
6. `agent_invocation` is a separate product ledger. It does not replace Product Task/Run state or canonical Product Events, and it must not create a second Product Run for a child invocation.
7. Invocation usage is attributed independently. Child usage may be aggregated into the Product Run only through an explicit, deterministic parent policy.
8. Language-only invocations use `workspace_access=none`, receive no physical directory, and receive no filesystem, Shell, network, or secret capability.
9. A future file-capable invocation must use a product-generated isolated workspace or governed Sandbox provider. Caller/model-selected roots, mounts, providers, and writable parent sharing are prohibited.
10. STEP040 creates and validates invocation identities and policy only. It does not execute a child Agent, native Handoff, nested Runner, Session, or physical workspace.
11. STEP041 Native Handoff and STEP042 Agent-as-Tool must reuse this ledger and may not introduce parallel child identity or workspace mechanisms.
12. Process-loss recovery, cancellation, approval, retention, Artifact transfer, streaming, and Evaluation for child invocations require explicit STEP coverage before being claimed.

## 18. Native Handoff Runtime constitution after STEP041

1. A native Handoff is one installed-SDK Runner execution inside one Product Task and Run; it must not create a second Product Run.
2. A Handoff destination resolves only from the immutable parent definition's closed `handoffs` graph. The model, Prompt, Tool arguments, API caller, and display name may not select an undeclared destination.
3. STEP041 permits exactly one sequential Handoff at depth one. Multiple, chained, recursive, or parallel Handoffs fail closed.
4. Product code must construct installed-SDK `handoff()` with the Runtime-bound input-filter and history policy. Executable code must never import Reference code.
5. At `on_handoff`, the current parent invocation is terminalized with cumulative usage and exactly one HANDOFF child invocation becomes RUNNING before the child continues.
6. Final child usage is the validated non-negative difference between final cumulative Run usage and parent cumulative usage. Product Run usage remains the final cumulative total.
7. Exactly one safe canonical `agent.handoff` Event records product Agent/invocation identity and policy evidence. Raw history, Handoff arguments, prompts, instructions, Tool data, and model output are prohibited.
8. Native `agent.updated` streaming may expose only safe child Agent identity and display metadata; raw Handoff items remain filtered by the STEP039 adapter.
9. Parent and child are language-only and use `workspace_access=none`. Native Handoff must not allocate or inherit a filesystem root, Sandbox, Shell, network, mount, or secret capability.
10. V1 forbids Handoff mixed with Function Tool, MCP, Agent-as-Tool, Session, approval interruption, or physical workspace.
11. Failure after transfer terminalizes the active child without rewriting the already successful parent invocation. Process-loss resume inside SDK Handoff is not claimed.
12. STEP042 Agent-as-Tool must reuse the same invocation ledger and may not copy the Handoff transition logic into a second identity or workspace implementation.

## 19. Agent-as-Tool Runtime constitution after STEP042

1. Agent-as-Tool is delegation with parent control retained; it is not a Handoff and must not reuse Handoff terminalization semantics.
2. A destination resolves only from the immutable parent's closed `agent_tools` graph. Model text may supply bounded input to the declared child but may not select an Agent definition, Python factory, provider, workspace, or policy.
3. STEP042 permits exactly one sequential Agent-as-Tool call at depth one inside one Product Task and Run. Multiple, recursive, parallel, or mixed child calls fail closed.
4. Product code must use installed-SDK `Agent.as_tool()` with an explicit child RunConfig. Implicit fallback to the parent's `ToolContext.run_config` is prohibited.
5. ROOT remains `RUNNING` while exactly one `AGENT_AS_TOOL` child invocation runs. Child completion returns a bounded structured JSON result to the parent, which then produces the Product final output.
6. Child usage is the non-negative cumulative SDK usage delta across the nested call. ROOT usage is final Product usage minus child usage. A second Product Run or an unproven estimate is prohibited.
7. Exactly one safe canonical `agent.tool.started` and `agent.tool.completed` pair records product Agent/invocation identity, policy evidence, child usage, and parent-control retention. Raw Tool arguments, call IDs, child items/results, prompts, instructions, reasoning, and secrets are prohibited.
8. Nested SDK streaming is ephemeral and may expose only safe child Agent identity, output text delta, and Run-item type/name metadata. It must not enter the canonical Event ledger.
9. Parent and child are language-only and use `workspace_access=none`; they receive no physical workspace, writable parent root, Sandbox, Shell, network, mount, or secret capability.
10. V1 forbids Agent-as-Tool mixed with Handoff, MCP, local Function Tool, Session, approval, or file capability.
11. Failure terminalizes the active child and ROOT through the shared STEP040 invocation ledger. Child process-loss resume or independent child retention is not claimed.
12. STEP043 Session must remain a separate lifecycle and must not silently add Session state to STEP042 parent or child execution.

## 20. SQLite Session Runtime constitution after STEP043

1. Session is ordered conversational history for one immutable Agent/Runtime binding; it is not long-term memory, workspace state, protected payload storage, or Product Task/Run state.
2. V1 uses the installed SDK `SQLiteSession`. Product code must pass the Session through the Runner `session=` argument and must not manually concatenate or copy history.
3. Product-owned Session metadata and SDK history use separate SQLite schemas/files and separate lifecycles.
4. Session creation requires both local-admin and Run-submitter authority and pins Agent Definition ID/version/SHA plus Runtime binding SHA.
5. Every governed Session Turn includes the Session ID in the request fingerprint and exact-confirmation boundary.
6. Exactly one Product Run may hold the active-Turn lease for a Session. Different concurrent Runs fail with `SESSION_BUSY`; clear is prohibited while active.
7. Successful Turns increment `turn_count` and synchronize SDK history `item_count`. Failed/cancelled Turns release the lease without incrementing successful Turn count.
8. Canonical `session.turn.started/completed` Events contain only Session identity, ordinal/counts, and no-history-copy evidence. Raw history and new input are prohibited.
9. Explicit clear removes SDK history and marks Product Session state `CLEARED`; historical Product Runs, Artifacts, Events and Evaluations remain immutable.
10. STEP043 history is local and unencrypted. Do not claim tenant-grade remote storage, retention automation, compaction, semantic memory, or cross-process lease.
11. Session-enabled Agents are tool-free, child-free, language-only, and `workspace_access=none` in V1. Mixing with Handoff, Agent-as-Tool, MCP, Function Tool, approval or workspace fails closed.
12. The Interactive Runner may create/select/clear Session metadata but must not persist or expose raw Session history in browser storage.
13. STEP044 Guardrail work must not silently combine Guardrails with Session. Guardrail acceptance uses a separate Session-disabled path.
## 21. Native Guardrail Runtime constitution after STEP044

1. SDK Guardrails are distinct from Pydantic schema validation, product authorization, exact confirmation, Tool JSON schema, and generic exception handling.
2. Guardrail definitions are immutable product-owned specifications under `specs/guardrails/<guardrail-id>` and resolve only through a closed implementation registry. Dynamic Python import, model-generated Guardrails, and caller-selected implementations are prohibited.
3. V1 supports exactly INPUT, OUTPUT, TOOL_INPUT, and TOOL_OUTPUT native SDK Guardrails with `RAISE_EXCEPTION` behavior. At most one of each kind may be attached to an Agent.
4. STEP044 input Guardrails use `run_in_parallel=false` so a tripwire occurs before model execution. Output Guardrails occur after final structured output but before Artifact registration.
5. Tool-input tripwire must occur before Tool implementation; Tool-output tripwire occurs after implementation. Tool-output rejection does not imply rollback of external effects, so V1 uses only the read-only capability-free `local_text_fingerprint` Tool.
6. Each rejected Run receives exactly one stable Product error code and one safe canonical `guardrail.tripped` Event. Raw guarded input/output, SDK `output_info`, Tool arguments/results, prompts, reasoning, call IDs, secrets and raw exceptions are prohibited from Product Events and Product/Evaluation DB.
7. A tripwire terminalizes the same Product Task, Run, Submission and active ROOT invocation as failed. It creates no Artifact or Evaluation, performs no retry/fallback/resume, and follows existing failed-payload investigation retention.
8. Guardrail definition SHA, kind, target Tool, behavior, implementation SHA and aggregate Runtime implementation are exact-confirmation-bound Runtime state. Drift requires a new preflight.
9. STEP044 Guardrail Agents are Session-disabled, child-free, MCP-free, approval-free and `workspace_access=none`. Mixing Guardrails with Session, Handoff, Agent-as-Tool, MCP, approval or physical workspace requires later explicit acceptance.
10. Marker-based Guardrails are deterministic acceptance policies only and must not be described as production semantic moderation.
11. Guardrail tripwire timing and safe Product evidence must be proven separately for input, output, Tool-input and Tool-output paths.
12. STEP045 must integrate the accepted capability surfaces without replacing Guardrail or any other primitive with demo-only shortcuts.


## 21. Integrated walking-skeleton constitution after STEP045

1. `specs/runtime/walking-skeleton-scenarios.json` is the closed product-owned P0 scenario catalog; browser input, prompts and model output may not create or mutate scenarios.
2. A Runner scenario selection may populate Agent, request template, Session requirement and Evaluation choice, but may never auto-confirm, auto-approve or invoke a hidden execution route.
3. `/runner`, `/console` and Approval Operator remain separate authority surfaces.
4. Native ephemeral SDK stream and canonical persisted Product Events remain visibly distinct.
5. ROOT, HANDOFF and AGENT_AS_TOOL invocation identities and workspace absence must be visible from Product state.
6. STEP045 acceptance may compose prior acceptance scripts only from the acceptance harness. Executable Runtime source must never invoke STEP scripts or substitute a demo execution engine.
7. `BASIC_AGENT_RUNTIME_SKELETON_COMPLETE` requires all ten catalog scenarios, all 28 STEP045 checks, all seven primitive reruns, Reference integrity and completed cleanup.
8. P0 completion does not imply arbitrary capability composition is supported. Mixed Session/child/Tool/approval, parallel children, physical workspace and hosted capabilities remain fail-closed until separately designed and accepted.
9. After STEP045 Windows closure, choose the next STEP only after a fresh code and Reference audit; do not continue depth-first merely because a candidate is listed in the roadmap.

## 22. SQLite Session + approval composition constitution after STEP046

1. Session+approval is an explicit composition of two accepted primitives; it is not permission for arbitrary mixed-capability Agents.
2. A Session approval Agent must declare exactly one product-owned Function Tool with `approval_mode=ALWAYS`, `session_mode=sqlite-v1`, no MCP, no Handoff, no Agent-as-Tool, no Guardrail and `workspace_access=none`.
3. The Session ID is immutable execution identity and must be bound in the governed request fingerprint, encrypted protected payload, submission ledger and approval record.
4. The Product Session active-Turn lease is acquired before SDK approval preparation and remains held while the Product Run is interrupted. Clear and another active Turn must fail during that interval.
5. Both initial prepare and RunState resume must receive the same installed-SDK Session. Product code must not manually concatenate history or create a second Session identity.
6. The pre-prepare SDK history item count is the rollback boundary. Integrity or resume failure removes later partial items and releases the Turn without incrementing `turn_count`.
7. An approved Turn commits exactly once, executes the Tool exactly once, and may create one Artifact and recorded Evaluation. Replay must add zero Tool calls, Session items, Turns or Artifacts.
8. A rejected conversational Turn commits the SDK rejection outcome exactly once, executes the Tool zero times, creates no Artifact/Evaluation and follows cancelled-run payload retention. Replay is a no-op.
9. Safe canonical events are exactly `session.turn.started`, `session.turn.interrupted` and `session.turn.completed`; raw history, request, Tool arguments/results, RunState, prompts, reasoning, call IDs and secrets are prohibited.
10. Approval inbox metadata may expose Session identity and counts needed for safe operation, but never Session history.
11. Session Product metadata, SDK history, approval ledger, protected payload, Product Task/Run, invocation, Artifact and Evaluation remain separate lifecycles and stores.
12. V1 claims no distributed transaction across Product and Session SQLite, no remote lease, no approval timeout automation and no in-flight process-loss auto-resume.
13. The immutable P0 walking-skeleton catalog remains exactly ten scenarios. STEP046 is a P1 composition and must not rewrite the P0 completion evidence.
14. After STEP046 Windows closure, choose the next executable STEP only after another code and Reference audit.

## 23. SQLite Session + native Handoff composition constitution after STEP047

1. Session+Handoff is one closed composition of two Windows-live accepted primitives; it does not enable arbitrary child graphs or mixed capabilities.
2. The root must declare `session_mode=sqlite-v1`, exactly one immutable native Handoff child, no Function Tool, MCP, Agent-as-Tool, Guardrail, workspace, Shell, file, network, or secret capability.
3. The child remains Session-disabled, terminal, capability-free, `workspace_access=none`, depth one, and must share the root structured output contract.
4. The same installed-SDK `SQLiteSession` is passed once to the root Runner and remains the SDK history authority across the transfer and later Product Turns. Product code must not copy or concatenate history.
5. One Product Session active-Turn lease is acquired before root execution and remains held through Handoff child completion, Artifact creation, and Session commit.
6. Each successful Turn performs exactly one native Handoff, creates one ROOT and one HANDOFF invocation, commits the complete SDK Turn, then increments `turn_count` once.
7. The history count before execution is the rollback boundary. Failed or cancelled composition execution removes later partial SDK items, releases the lease, and does not increment `turn_count`.
8. Canonical Events expose only safe Session and Handoff identity/policy metadata. Raw Session history, request text, Handoff payload/history, prompts, reasoning, model deltas, and secrets remain outside Product and Evaluation storage.
9. Confirmation replay must not schedule a second Run, create a second child invocation, append history, or duplicate Artifact/Evaluation state.
10. Session metadata/history, Product state, invocation ledger, protected payload, Artifact, Evaluation, and acceptance workspace remain separate lifecycles.
11. STEP047 does not support Session+Agent-as-Tool, Session+MCP, Session+Guardrail, Session+Function Tool other than STEP046, multiple/nested/parallel Handoffs, physical workspace, remote Session backend, distributed lease, or process-loss resume.
12. STEP047 is Windows-live accepted from the reported 29/29 launcher result. Later compositions must preserve this exact Session/Handoff boundary and evidence.


## 24. SQLite Session + native Guardrail composition constitution after STEP048

1. Session+Guardrail is one closed language-only composition of independently Windows-live accepted primitives; it does not enable arbitrary mixed capability graphs.
2. The Agent must declare `session_mode=sqlite-v1`, at most one INPUT Guardrail and one OUTPUT Guardrail, no Function Tool, Tool Guardrail, MCP, Handoff, Agent-as-Tool, workspace, Shell, file, network, hosted Tool, or secret capability.
3. The installed SDK `SQLiteSession` remains the sole conversational-history authority. Product code must not concatenate, reconstruct, or copy raw Session history.
4. Product acquires the active-Turn lease and captures the exact pre-Turn SDK item count before `Runner.run_streamed`.
5. A successful guarded Turn commits exactly once, creates one Artifact, increments `turn_count` once, and synchronizes the observed SDK item count.
6. An INPUT or OUTPUT tripwire is a failed Product Turn. Every SDK item after the captured pre-Turn boundary must be removed before lease release, and `turn_count` must not increase.
7. Rollback must be boundary-based, not based on guessing whether the SDK persisted a user item, assistant item, or complete pair before raising.
8. Each rejection records one exact stable Guardrail error code and one safe `guardrail.tripped` Event. Guarded input/output, prompts, instructions, reasoning, SDK output info, and API keys are prohibited from Product and Evaluation storage.
9. Rejected Turns create no Artifact or Evaluation and retain protected payload only under the existing failed-run investigation policy; successful payloads are deleted.
10. Confirmation replay must schedule no second execution and add no Session items, Turn, Artifact, Evaluation, or duplicate Guardrail Event.
11. Session metadata/history, Product Task/Run, invocation, protected payload, Artifact, Evaluation, and acceptance workspace remain distinct lifecycles and stores.
12. STEP048 claims no Tool Guardrail composition, operator override, retry/fallback after tripwire, distributed transaction, remote Session backend, encryption, compaction, export, distributed lease, or process-loss automatic resume.
13. STEP048 is Windows-live accepted from the reported complete 32/32 launcher result. Later compositions must preserve its exact successful-commit and tripwire-rollback boundary.

## 25. SQLite Session + native Agent-as-Tool composition constitution after STEP049

1. Session+Agent-as-Tool is one closed Root-owned conversation composition of independently Windows-live accepted primitives; it does not enable arbitrary nested Agent graphs or capability mixing.
2. The Root must declare `session_mode=sqlite-v1`, exactly one immutable Agent-as-Tool child, no Function Tool, approval, MCP, Handoff, Guardrail, workspace, Shell, file, network, hosted Tool, Sandbox, or secret capability.
3. The child must remain `session_mode=disabled`, terminal, language-only, depth one, `workspace_access=none`, and share the Root structured output contract.
4. The installed SDK SQLiteSession is passed only to the outer Root Runner. The nested `Agent.as_tool` run must receive `session=None`; Product code must never share the Root Session object with the child or create an implicit child Session.
5. Product acquires one Root active-Turn lease and captures the exact pre-Turn SDK item count before outer execution. The lease remains held through nested child completion, Root continuation, Artifact creation and Session commit.
6. Each successful Turn performs exactly one Agent-as-Tool call, creates one ROOT and one AGENT_AS_TOOL invocation, retains parent control, commits the complete Root SDK Tool conversation, then increments `turn_count` once.
7. The child uses an explicit non-inherited RunConfig and may return only the bounded structured result allowed by the existing STEP042 Agent-as-Tool policy.
8. Parent or child failure removes every outer Session item after the captured pre-Turn boundary before lease release; `turn_count` must not increase.
9. Canonical Events expose only safe Session, Agent, invocation, policy and bounded lifecycle metadata. Raw Session history, request text, child arguments/results, nested output, prompts, reasoning, SDK objects and secrets remain outside Product and Evaluation storage.
10. Confirmation replay must not schedule a second execution, create another child invocation, append history, or duplicate Artifact/Evaluation state.
11. Session history, Product Task/Run, invocation ledger, protected payload, Artifact, Evaluation and acceptance workspace remain distinct lifecycles and stores.
12. STEP049 does not support Session-enabled children, more than one Agent Tool call, deeper or parallel nesting, Handoff mixing, physical workspace, remote Session backend, distributed lease, process-loss resume, retry/fallback, or distributed atomicity.
13. The first STEP049 Windows attempt passed every functional check but failed cleanup because the Acceptance-only direct SQLite history probe left `history.sqlite3` open. `with sqlite3.connect(...)` is not a close boundary. The corrected probe must close in `finally`, and this failure evidence must remain recorded.
14. STEP049 is Windows-live accepted from the corrected-package 33/33 result with cleanup `COMPLETED` in one attempt. The prior preserved-workspace failure remains evidence of the fixed Acceptance-only SQLite connection leak.



## 26. SQLite Session + native MCP composition constitution after STEP050

1. Session+MCP is one closed composition of the installed-SDK SQLite Session and one existing product-owned, allowlisted, read-only local stdio MCP server; it does not authorize arbitrary MCP breadth.
2. The Agent must declare `session_mode=sqlite-v1`, exactly one `reference-catalog` MCP server, `workspace_access=none`, and no Function Tool, approval, Handoff, Agent-as-Tool, Guardrail, file, Shell, hosted Tool, Sandbox or secret capability.
3. The MCP transport must be product-defined `builtin-stdio`, local and read-only. Callers, prompts, model output and Tool arguments may not select executable modules, commands, transports or servers.
4. Product acquires one active-Turn lease and captures the exact pre-Turn SDK item count before entering the per-Turn MCP manager. The same installed-SDK Session is passed only to the outer `Runner.run_streamed()` execution.
5. MCP manager ownership is per Turn. The Turn lease remains held until the manager exits, the Runner result is terminal, success is committed or failed history is rolled back, and Session metadata is synchronized.
6. A successful Turn performs exactly one MCP Tool call, commits the complete four-item SDK Tool conversation, creates one Artifact and increments `turn_count` once.
7. MCP or Runner failure exits the manager first, removes every SDK item after the captured pre-Turn boundary, creates no Artifact/Evaluation, does not increment `turn_count`, and only then releases the lease.
8. Rollback ordering is evidence-bearing: manager cleanup must precede history pop operations. Final item counts alone are insufficient proof.
9. Canonical Events expose only safe MCP server ID, Tool name and lifecycle metadata. Queries, Tool arguments/results, Session history, prompts, reasoning, SDK objects and secrets remain outside Product and Evaluation storage.
10. Confirmation replay must not start another manager, execute another MCP Tool, append history, or duplicate Artifact/Evaluation state.
11. Successful payloads are deleted; failed payloads follow the existing bounded investigation-retention policy. Session history, MCP process lifecycle, Product Run, payload, Artifact, Evaluation and acceptance workspace remain distinct stores and lifecycles.
12. STEP050 does not support remote MCP, OAuth, resources/prompts/subscriptions, multiple servers, write-capable Tools, retries/reconnect, arbitrary capability mixing, physical workspace, process-loss resume, distributed lease or distributed atomicity.
13. STEP050 is Windows-live accepted from the reported 31/31 result with cleanup `COMPLETED` in one attempt. Later work must preserve the manager-exit-before-rollback order and exact Session/MCP boundary.


## 27. Immutable OpenAI model route constitution after STEP051

1. Model routing is a product-owned immutable execution boundary, not an SDK/environment default and not a caller-selected provider string.
2. STEP051 permits exactly provider `openai`, installed-SDK `OpenAIProvider`, Responses API, HTTP transport and official base URL `https://api.openai.com/v1`.
3. The concrete model ID must be explicit, bounded by the policy pattern and contain no provider prefix separator `/`. Provider aliases, provider matrices and custom endpoints are forbidden.
4. Governed preflight resolves the model route before persistence. A denied route returns validation status 422 and creates no submission row.
5. Runtime binding must include the canonical model-routing policy SHA and the combined source SHA of the product-owned model-routing models, catalog and provider wrapper.
6. Confirmation must recompute that binding. Policy or provider-source drift fails closed before Task/Run creation and leaves only the existing encrypted unconfirmed payload lifecycle.
7. Every SDK execution uses explicit `RunConfig.model` and `RunConfig.model_provider`; SDK default provider resolution is not authoritative. Nested Agent-as-Tool runs receive the same explicit immutable provider.
8. The provider wrapper forces Responses HTTP, disables Responses WebSocket, enables strict feature validation and accepts only the exact resolved model.
9. Automatic fallback and fallback model lists are forbidden. No retry may silently change provider, endpoint or model identity.
10. Sensitive trace data is disabled. Product Events may expose only safe route identity, policy SHA and selected model; endpoint, API key, prompts, responses and reasoning are prohibited.
11. Provider resources must close in the gateway outer `finally` after Runner and MCP lifecycles terminate; close must be idempotent.
12. STEP051 does not support Claude, Gemini, LiteLLM, AnyLLM, Azure/custom endpoints, dynamic aliases, pricing/budget/quality routing, fallback, WebSocket, secret management or cross-provider replay equivalence.
13. STEP051 is Windows-live accepted from the reported complete 25/25 launcher result with provider construct/get-model/close `1/1/1`, policy drift `409`, exact Product counts and cleanup `COMPLETED` in one attempt. Later model-policy work must preserve its immutable OpenAI Responses/HTTP route, explicit provider, no-fallback and provider-close boundary.

## 28. Immutable OpenAI zero-retry constitution after STEP052

1. Model retry authority is Product-owned and Runtime-bound; SDK/provider defaults are not authority.
2. Provider-managed and Runner-managed model retry budgets are both exactly zero.
3. The OpenAI client must be constructed with `max_retries=0` and the SDK RunConfig must carry explicit `ModelRetrySettings(max_retries=0, policy=never)`.
4. The installed SDK conversation-locked compatibility retry path must remain disabled through the explicit zero retry budget.
5. No model, provider, Product Run, Task, Tool, Handoff, MCP call or Session Turn may be automatically replayed after a model failure.
6. A model failure terminalizes the same Product Run and follows existing failed-payload retention. It creates no Artifact or Evaluation.
7. Retry policy and retry implementation source identity are part of the Runtime binding. Drift requires a new preflight and confirmation.
8. Safe Events may expose policy ID/SHA and numeric retry budgets only. Raw error, endpoint, request, response and secret are prohibited.
9. Positive retry, backoff, provider advice, HTTP status retry, model fallback and replacement execution require a later separately accepted constitution.
10. STEP052 is Windows-live accepted from the reported complete 25/25 launcher result with provider/Runner retry budgets `0/0`, model attempts `2`, drift `409`, exact Product counts and cleanup `COMPLETED` in one attempt. Later model-execution work must preserve exact zero retry unless a separate positive-retry constitution is implemented and accepted.


## 29. Immutable reasoning evidence minimization constitution after STEP053

1. Reasoning evidence handling is Product-owned, immutable and Runtime-bound; SDK/provider response richness is not permission to persist reasoning material.
2. STEP053 explicitly requests no reasoning summary and no additional reasoning response includes: `reasoning=None` and `response_include=[]` are supplied through SDK `ModelSettings`.
3. Product, Event, Artifact and Evaluation storage must never persist reasoning content, reasoning summaries, reasoning item IDs, encrypted reasoning content or reasoning provider data.
4. Reasoning items may be observed only by safe type inspection to produce an aggregate item count. Counting code must not read sensitive reasoning fields.
5. Aggregate numeric `reasoning_tokens` from SDK usage may be persisted. It is accounting evidence, not reasoning content.
6. Safe model Events may expose policy ID/SHA, boolean minimization controls, response-include count, reasoning item count and aggregate reasoning token count only.
7. Runtime binding must include the canonical reasoning-evidence policy SHA and combined source SHA of its product-owned models, catalog and runtime implementation.
8. Confirmation recomputes that binding. Policy or source drift fails closed before another Task/Run is created.
9. The immutable OpenAI Responses/HTTP route, explicit provider, zero-retry policy, no fallback, sensitive trace disablement and provider-close boundary remain mandatory.
10. STEP053 does not expose chain of thought, reasoning summaries, encrypted reasoning, provider-specific reasoning payloads, configurable reasoning effort, positive retry, alternate providers or reasoning export.
11. STEP053 is Windows-live accepted from the reported complete 30/30 launcher result with reasoning item/token evidence `1/11`, drift `409`, exact Product counts and cleanup `COMPLETED` in one attempt. Later model-request work must preserve its reasoning minimization boundary.


## 30. Immutable OpenAI Responses storage-disabled request constitution after STEP054

1. The OpenAI Responses request-level storage choice is Product-owned, immutable and Runtime-bound; an SDK/provider default is not authority.
2. STEP054 permits exactly `response_store_requested=false`, represented by installed-SDK `ModelSettings.store=False`.
3. Every `ModelSettings` constructed by the generic OpenAI gateway, including explicit Agent-as-Tool child and Tool-bearing Agent settings, must carry the false value.
4. Runtime binding must include the canonical response-storage policy SHA and combined source SHA of the product-owned models, catalog and runtime implementation.
5. Confirmation recomputes that binding. Policy or source drift fails closed before another Product Task/Run is created.
6. Safe model Events may expose policy ID/SHA and the false request value only. They must not imply universal provider erasure or zero operational retention.
7. The immutable official OpenAI Responses/HTTP route, explicit provider, zero retry, no fallback, reasoning minimization, sensitive trace disablement and provider-close boundary remain mandatory.
8. `store=False` is a request-level API control. It does not govern provider abuse-monitoring, billing or legal records, prompt-cache retention, provider response/request identifiers or account-level data-control settings.
9. STEP054 does not add positive retry, another provider, remote MCP, Session transformation, parallel execution or Sandbox capability.
10. STEP054 is Windows-live accepted from the reported complete 30/30 launcher result with exact `store=false`, drift `409`, Product counts and cleanup `COMPLETED` in one attempt. Later work must preserve this request-level storage boundary and its claim limitation.


## 31. Immutable OpenAI provider identifier minimization constitution after STEP055

1. Provider response/request identifier persistence is Product-owned, immutable and Runtime-bound; SDK result richness is not permission to retain correlation identifiers.
2. STEP055 permits exactly `persist_response_id=false`, `persist_request_id=false`, and `persist_identifier_presence=true`.
3. The installed SDK may use response/request identity transiently during one active execution. Product code must discard `RunResult.last_response_id` when crossing the gateway result boundary.
4. `model.completed` may expose only `response_id_present` and `request_id_present` booleans plus explicit false persistence flags. Raw `response_id` and `request_id` fields are prohibited.
5. Product Run Events, Product DB, Evaluation DB, Artifact, Runtime binding and generic execution response must contain no raw provider response/request identifier. A null optional response field is not identifier evidence.
6. Runtime binding must include the canonical provider-identifier policy SHA and combined source SHA of its product-owned models, catalog and runtime implementation.
7. Confirmation recomputes that binding. Policy or source drift fails closed before another Product Task/Run is created.
8. The official OpenAI Responses/HTTP route, explicit provider, zero retry, no fallback, reasoning minimization, `store=false`, sensitive trace disablement and provider-close boundary remain mandatory.
9. STEP055 does not claim provider-side identifier absence, transport zero logging, SDK in-memory nonexistence, trace-ID removal or prompt-cache control.
10. STEP055 is Windows-live accepted from the reported complete 35/35 launcher result with presence-only provider identifier evidence true/true, exact Product counts, drift `409`, Reference integrity and cleanup `COMPLETED` in one attempt. Later provider work must preserve this minimization boundary.

## 32. Governed TUI Client constitution after STEP056

1. The TUI is a client of the existing loopback Control API; it is not a second Runtime, scheduler,
   policy engine, Session store, approval engine, or execution gateway.
2. TUI credentials may be sent only to an explicit loopback URL with an explicit port. Remote hosts,
   URL credentials, path components, query strings, and fragments fail closed.
3. Local administrator and Run-submitter authorities remain distinct. Keys may come only from the
   process environment or non-echo terminal input and must not be written to disk, embedded in a URL,
   printed, or persisted in Product/Evaluation state.
4. STEP056 execution is limited to tool-free, Session-disabled, workspace-free Agents with no MCP,
   Handoff, Agent-as-Tool, or Guardrail. The TUI must not silently execute an unsupported Agent.
5. Every Run must use the existing governed preflight and exact confirmation endpoints. The TUI may
   compare the challenge locally, but the Control API remains the final authority.
6. A local confirmation mismatch must call no confirmation endpoint and create no Product Task/Run.
   The existing preflight and protected-payload retention policy remains authoritative.
7. Persisted canonical SSE is the V1 live view. The TUI must validate Run identity, preserve sequence
   order, and fetch the terminal Product Run after stream completion.
8. The TUI may display only Control API Agent, Event, Invocation, verified Artifact, and recorded
   Evaluation contracts. It must not open Product/Session/Evaluation SQLite directly or read Artifact
   storage paths.
9. The TUI must not import Agent SDK Runner, execution gateways, Tool/MCP implementations, protected
   payload stores, Runtime binding calculators, or executable code from `/reference`.
10. STEP056 does not authorize Session UI, approval decisions, Tool/MCP execution, native SDK stream,
    cancellation, reconciliation, Sandbox, filesystem, Shell, network, or workspace capability.
11. STEP056 is deterministic-accepted only after its loopback HTTP, persisted SSE, Artifact,
    Evaluation, credential non-persistence, exact counts, Reference integrity, and cleanup checks pass.
12. STEP057 selection remains blocked until a fresh STEP056 package is Windows-live accepted. The
    intended product sequence is TUI Session/Approval, observed Sub Agent/Tool gaps, and only then a
    separately governed Sandbox master plan.


## 33. STEP056 local environment startup constitution correction

1. The local Control API launcher must validate its non-secret configuration shape before uvicorn is started.
2. Example placeholders are never valid administrator or Run-submitter secrets. Both authorities must contain at least 16 characters and remain distinct.
3. `OKCANVAS_PROTECTED_PAYLOAD_KEY` must be either 64 hexadecimal characters or URL-safe base64 that decodes to exactly 32 bytes.
4. Validation errors must not print the configured secret value and must return before a socket is opened.
5. The product-owned AES-256-GCM key parser remains the final cryptographic authority; launcher validation is an equivalent early diagnostic, not a second key policy.
6. `.env.local.example` is the only canonical local environment template. `.env.example` and `.env.local.cmd.example` must not be shipped as competing templates.
7. A protected-payload key must not be rotated while encrypted local payloads still need to be read. Fresh generation is appropriate for fresh local state or an invalid placeholder that never encrypted valid data.
8. STEP056 technical Windows acceptance is now closed from the reported 21/21 result. Its Python single-run client is retained only as historical transport evidence, not as the product CLI.


## 34. Node.js/TypeScript persistent Agent CLI constitution after STEP056B

1. At STEP056B, `clients/okcanvas-agent-cli` was the local terminal product surface. Section 44 supersedes that classification: it is now retained only as a development/acceptance harness, while final service clients live under separate `agent-cli/`, `agent-web/`, and `agent-desktop/` roots. Python `tui_client` remains historical STEP056 smoke evidence.
2. `sh_tui.cmd` must launch the compiled Node CLI directly and must not route the user-facing client through Python or the project virtual environment.
3. The CLI is one long-lived process. It must return to the prompt after every completed request and remain active until `/quit`, EOF, or Ctrl+C.
4. The first foundation supports only tool-free, Session-disabled, workspace-free Agents. Repeated prompts share a client process but do not imply server conversation memory. This limitation must be displayed at startup.
5. The CLI must use only the loopback Control API and persisted SSE. It may not import Python Runtime modules, inspect SQLite, read protected payloads, execute Agent SDK code, or run `/reference` code.
6. Every Run still uses governed preflight and the exact server challenge. The user approves with a simple local yes/no decision; the CLI sends the exact challenge without printing or asking the user to copy it.
7. General mode must not require or create a recorded Evaluation. Evaluation is explicit opt-in only.
8. Normal output is the readable Artifact result. Run IDs, Events, raw JSON, Artifact SHA and Evaluation details remain hidden until `/details`, `/events`, or `/json`.
9. The package must define an npm-compatible `bin` and retain compiled `dist/` in the source ZIP. Immediate npm publication, global install, auto-update and executable bundling are deferred.
10. Runtime npm dependency count is zero in this foundation. Node standard APIs own HTTP, SSE, readline, filesystem and UUID behavior.
11. `.env.local.example` is the sole root template. `sh_init_local_env.cmd` creates `.env.local` with distinct admin/submitter authorities and a valid 32-byte payload key without printing secrets.
12. STEP056B is deterministic-accepted only after one Node process executes at least three governed requests, returns to the prompt after each, hides raw challenges, creates zero default Evaluations, preserves exact Product counts, leaves no successful payloads, preserves References and cleans up.
13. STEP057 remains blocked until the complete STEP056B Windows result is reported from the packaged Node CLI. The next intended slice is real Runtime Session continuity in the persistent CLI, followed by observed Tool/Sub Agent needs and only later Sandbox.

## 35. Node.js/TypeScript Agent CLI developer observability constitution after STEP056C

1. At STEP056C, the Node.js/TypeScript persistent CLI was the local terminal product surface. Section 44 supersedes that classification and retains it only as a development/acceptance harness; the Python STEP056 client remains historical transport-smoke evidence only.
2. Normal mode is answer-first and developer diagnostics are off by default.
3. `--debug` and `/debug on|off` may expose governed preflight, exact local confirmation challenge, persisted SSE, terminal Run, verified Artifact raw JSON and Evaluation state.
4. Debug visibility must never require the user to copy or retype the exact challenge. The client transmits the exact server value only after local `Y/n` consent.
5. Debug output may contain Product identifiers and Runtime binding SHA but may never print administrator, submitter, provider API or protected-payload secrets.
6. Evaluation remains off by default. `/evaluate <case-id>` is an explicit post-Run operation through the existing Control API.
7. `/status` must expose only safe Runtime URL/version, active Agent/model, debug state, Session state, Evaluation default and last Run identity.
8. When several compatible Agents exist, the CLI may not silently select the first catalog entry. Use `--agent-id`, `OKCANVAS_DEFAULT_AGENT_ID`, a sole compatible Agent, or explicit interactive selection in that order.
9. STEP056C must remain Control-API/SSE-only with no Python Runtime import, SQLite, Agent SDK, Tool/MCP or Reference execution access from Node.
10. STEP057 remains blocked until the complete packaged STEP056C Windows acceptance is reported.

## 36. Node CLI Runtime Session conversation constitution after STEP057

1. At STEP057, the local terminal surface remained the separate Node.js/TypeScript package under `clients/okcanvas-agent-cli`. Section 44 supersedes that classification and reserves final service-client products for `agent-cli/`, `agent-web/`, and `agent-desktop/`.
2. The CLI may use only the loopback Control API and persisted SSE; it may not import Python Runtime code or open SQLite directly.
3. `conversational-coding-agent` is the product-owned canonical text-only Session Agent. It has no Tool, MCP, Handoff, Agent-as-Tool, Guardrail, workspace, Shell, network or Sandbox access.
4. A Session-enabled Agent must have one exact Runtime Session before governed preflight, and every Turn must send that exact `session_id`.
5. Agent/Runtime binding validation, one-active-Turn lease, history persistence, rollback and clear authority remain server-owned.
6. The CLI may create, list, inspect, resume and clear Sessions only through `/v1/sessions` APIs.
7. The CLI must never expose raw historical SDK Session items automatically. `/history` is current-process rendered transcript only.
8. `/new` creates a separate Session and must not inherit prior history. `/resume` must verify ACTIVE state and exact Agent identity.
9. A CLI restart may resume only an explicit Session ID; no hidden local state file may silently select a previous Session in STEP057.
10. Evaluation remains off by default and must not be confused with Run or Artifact success.
11. STEP058 must not be selected before complete packaged STEP057 Windows acceptance is reported.
## 37. STEP057 default Agent environment allowlist correction

1. `.env.local.example` remains the single canonical local environment template and may include `OKCANVAS_DEFAULT_AGENT_ID=conversational-coding-agent`.
2. Every Windows launcher that loads `.env.local` must accept `OKCANVAS_DEFAULT_AGENT_ID` through the shared non-executing environment parser.
3. The default-Agent setting is a client selection preference only; it does not grant Runtime authority, change Agent definitions, bypass compatibility checks, or alter Session ownership.
4. Unsupported environment names remain rejected. Adding this exact key must not broaden the parser to arbitrary variables.
5. STEP057 Windows closure requires rerunning API startup, Node CLI startup, and the complete STEP057 acceptance from the corrected package.


## 38. Node CLI Tool and Sub Agent workflow visibility constitution after STEP058

1. STEP058 exposes only capability paths already accepted by the Runtime: one approval-free read-only local Function Tool, one native Handoff, or one Agent-as-Tool child.
2. The Node CLI remains a Control-API/persisted-SSE client and must not import Python Runtime code, open SQLite, execute Tool code, or calculate Runtime bindings.
3. A CLI-compatible Function Tool Agent must declare exactly one Tool whose public capability is `approval_mode=NEVER`, `read_only=true`, and filesystem/network/Shell access all `none`.
4. Approval-required Tools, MCP, Guardrails, workspace access, mixed capability families, multiple Tools, deeper graphs, parallel children, Shell, network and Sandbox remain excluded.
5. Handoff and Agent-as-Tool Agents may expose exactly one immutable child edge. Existing Session-enabled Handoff and Agent-as-Tool compositions remain eligible without changing their server-owned policies.
6. Normal answer-first mode may display only safe lifecycle progress: Tool name, source/target Agent IDs, completion state and terminal invocation structure. Raw Tool arguments/results, child content, Session history, prompts, reasoning and secrets remain hidden.
7. `/invocations` displays the Product-owned invocation ledger only. It must not reconstruct SDK history or nested raw outputs.
8. Agent selection surfaces the Session mode and capability path so users know whether a selected Agent is text-only, Tool-bearing, Handoff-based or Agent-as-Tool-based.
9. STEP057 is Windows-live accepted from the reported manual memory probe and complete 25/25 acceptance result. Later work must preserve exact Session resume and new-Session isolation.
10. STEP059 must not be selected before complete STEP058 Windows acceptance is reported.

## 39. Bounded project read-only coding workflow constitution after STEP059

1. STEP058 is Windows-live accepted from the complete reported 18/18 Tool/Handoff/Agent-as-Tool CLI result.
2. `project-readonly-coding-agent` is the only STEP059 project-inspection Agent and declares exactly one `project_readonly_inspect` Function Tool.
3. The inspected root is server-owned `OKCANVAS_READONLY_WORKSPACE_ROOT`; the model and Node CLI may not supply or change a filesystem root.
4. The Tool is approval-free and read-only with filesystem access `read-only`, network `none`, Shell `none`, raw arguments not persisted and raw results not persisted in Events.
5. Traversal follows no symlinks, rejects a symlink root, excludes dependency/generated/local-state/immutable-Reference directories and returns repository-relative paths only.
6. Hard limits are 3,000 candidate text files, 32 MiB aggregate input, 512 KiB per file, 12 evidence files, 40 lines and 4,000 characters per excerpt.
7. The Node CLI may display bounded finding evidence locations but must not automatically print Tool excerpts, absolute workspace paths, raw Tool arguments/results or secrets.
8. STEP059 adds no file write, delete, rename, Shell, process, Git command, network, web, MCP, Approval, Handoff, Agent-as-Tool, Guardrail, Session or Sandbox capability.
9. One API process owns one configured root. Changing projects requires configuration change and API restart; multi-root selection is deferred.
10. STEP059 is deterministic-accepted only when an actual fixture project is inspected, excluded dependency data is unread, fixture bytes remain identical, relative evidence is visible, exact Product counts hold, payload cleanup completes and immutable References remain unchanged.
11. STEP060 must not be selected before complete packaged STEP059 Windows acceptance is reported.

## 40. Actual SDK Function Tool output-contract constitution after STEP059A

1. The installed `openai-agents==0.19.0` SDK and the immutable SDK Reference are the authority for Function Tool decorator contracts.
2. `output_type` and `output_json_schema` are mutually exclusive. Product code must never pass both.
3. Product Function Tools bind `output_type=runtime.output_model` only so strict schema generation and output validation share one Pydantic authority.
4. Fake SDKs used by tests must reject dual output binding exactly as the real SDK does; permissive fakes are not sufficient acceptance evidence.
5. STEP059A Windows acceptance must import the installed SDK and construct every registered Product Function Tool without a model call.
6. A successful construction-only gate does not replace one real governed OpenAI Tool run through the Node CLI.
7. STEP060 remains blocked until both the actual-SDK construction gate and the real project-readonly Tool run are reported successful.

## 41. Actual SDK ToolContext export constitution after STEP059B

1. Immutable `openai-agents-python-0.19.0` source is the authority for SDK export paths.
2. `function_tool` is imported from top-level `agents`; `ToolContext` is imported from
   `agents.tool_context` and must not be expected at top level.
3. Fake SDKs must mirror the real package/module export structure. They may not add permissive
   top-level symbols that hide Product import defects.
4. STEP059A output-type-only binding remains mandatory and unchanged.
5. Windows actual-SDK acceptance must construct all registered Product Function Tools and one
   actual SDK Agent without a network model call.
6. A successful construction gate still does not replace one real governed OpenAI Tool execution.
7. STEP060 remains blocked until STEP059B actual-SDK construction and real project-readonly CLI
   execution both pass.

## 42. Query-directed project retrieval and evidence-budget constitution after STEP060

1. STEP059B actual SDK Tool construction and one real project-readonly OpenAI Tool run are Windows-live accepted.
2. A successful Tool lifecycle is not sufficient product quality when a narrow question receives irrelevant evidence, PARTIAL output, or excessive model context.
3. `project_readonly_inspect` remains the sole project Tool and the server-configured root remains the only filesystem authority.
4. Retrieval must normalize bounded Korean/English query terms, down-weight common corpus terms, and score the best line window rather than whole-file occurrence counts.
5. Route-registration and definition-location structure may influence ranking only through static text patterns; no code, AST, process, import, Git command or language server may execute.
6. Implementation source is preferred by default. Tests, documentation, or clients become the preferred surface only when the user explicitly targets that surface.
7. The Tool returns at most four evidence files, 16 lines and 1,600 characters per excerpt, and 5,000 aggregate evidence characters.
8. The Agent must answer only the exact question, name the exact repository-relative file/line first for location requests, use no more than three findings, and suppress unrelated architecture/security/history/readiness audits.
9. All STEP059 read-only, symlink, exclusion, relative-path, no-persistence, no-Shell, no-network and no-write boundaries remain mandatory.
10. STEP060 Windows closure requires deterministic 20/20 acceptance and one real OpenAI rerun with Artifact PASS, exact implementation evidence, no unrelated audit, and total usage at or below 5,000 tokens.
11. STEP061 remains blocked until the complete STEP060 Windows result is reported.

## 43. OpenAI Agents SDK examples coverage constitution after STEP061

1. The authoritative SDK capability inventory is
   `docs/reference/STEP061_OPENAI_AGENTS_EXAMPLES_COVERAGE_MATRIX.json`.
2. The immutable SDK examples tree contains 216 Python files; exactly four root runner/support files
   are excluded, leaving 212 classified capability/example files across 15 areas.
3. Every classified file must have an exact SHA-256, line count, observed SDK symbols, one of
   `ADOPT|ADAPT|DEFER|REJECT`, a target track, and a code-derived rationale.
4. Summary claims must be generated from the file-level entries; never hand-edit counts independently.
5. `ADOPT` means the SDK primitive is directly wired. `ADAPT` means only a narrower product-owned
   pattern is present. Neither decision permits copying executable code from `/reference`.
6. `DEFER` does not authorize implementation. Each deferred capability requires a separate audited
   STEP and authority design.
7. `REJECT` remains binding until a later constitution explicitly replaces it. Current rejections
   include hosted multi-agent beta, non-strict output, provider response-ID continuity, hidden model
   retries, and reasoning-content persistence.
8. The only selected next implementation is
   `STEP062_BOUNDED_MULTI_AGENT_ORCHESTRATION_FOUNDATION`.
9. STEP062 must extend the Product invocation ledger and must not introduce a separate ungoverned
   workflow engine.
10. STEP062 V1 is a closed depth-1 graph with fixed read-only sibling Agents, bounded parallelism,
    deterministic product-owned aggregation, explicit partial-failure/cancellation policy, and one
    verified root Artifact.
11. STEP062 must not add Session, approval, MCP/network expansion, writable workspace, dynamic Agent
    discovery, planner-generated arbitrary children, or LLM judging as authority.
12. STEP061 deterministic and Windows 20/20 acceptance are complete; its matrix and decisions remain immutable predecessor evidence.


## 44. Bounded multi-Agent orchestration constitution after STEP062

1. STEP061 is Windows-live accepted from the user-reported complete 20/20 result.
2. STEP062 V1 has exactly one logical root and exactly two immutable terminal sibling Agents. Child count, declaration order, maximum parallelism two and maximum depth one are policy-bound.
3. The logical root performs zero model calls. Product Runtime code, not a manager model, starts child SDK Agents, owns failure/cancellation, aggregates results and creates the root Artifact.
4. Each child executes through an independent direct `Runner.run()` call under the same Product Run group and trace ID. `Runner.run_streamed()` and native child delta streaming are disabled.
5. The existing Product Task/Run/Event/Artifact and Invocation ledger remain authoritative. Child executions never create independent Product Runs.
6. The invocation ledger contains one ROOT and two `ORCHESTRATION_CHILD` rows. Root token usage is zero; Run usage is the exact sum of child usage.
7. Runtime failure policy is `ALL_REQUIRED_FAIL_FAST`. An unfinished sibling receives cancellation, failed/cancelled states are persisted, the root Run fails and no Artifact is created.
8. Business status `FAIL` inside a valid `CodingAgentResult` is not a Runtime failure. Complete child results are still aggregated and the root business status becomes the maximum severity.
9. Aggregation is `DECLARATION_ORDER_STRUCTURED`. Completion order, task scheduling and model wording may not reorder child entries or determine the aggregate summary format.
10. The root output contract is `BoundedOrchestrationResult`; child output is `CodingAgentResult`. Exactly one verified aggregate Artifact is permitted on complete success.
11. Root and children are Session-disabled, workspace-free and declare no Function Tool, approval, MCP, Handoff, Agent-as-Tool, Guardrail, filesystem, Shell, network expansion or Sandbox capability.
12. Dynamic child discovery, variable child count, nested graph, planner-generated tasks, collect-partial execution, LLM judge authority, model-owned aggregation, retries and provider fallback remain forbidden.
13. Public definition APIs and clients may expose only child IDs, ordinal, state, safe usage and aggregate summaries. Raw child output, prompt, reasoning, provider IDs and secrets remain absent from lifecycle Events.
14. Any root, child, policy, implementation or child Runtime binding change must alter the root Runtime binding SHA and require fresh governed confirmation.
15. STEP062 is deterministic-accepted only after concurrent overlap, reverse-completion ordering, exact ledger usage, success Artifact, failure cancellation, API/CLI visibility and full regression are proven.
16. STEP063 must not be selected before complete STEP062 Windows acceptance is reported and a fresh code audit is performed against the packaged ZIP.

## 45. Strict encrypted SQLite Session history constitution after STEP063

1. STEP062C and its embedded STEP062B/062A/062 closures are Windows-live accepted. Bounded orchestration remains unchanged.
2. Every newly created `sqlite-v1` Product Session requires an external `OKCANVAS_SESSION_HISTORY_KEY` that decodes to exactly 32 bytes from 64-hex or URL-safe base64.
3. The Session history key is never persisted. Only its non-secret 16-hex SHA-256 key ID is stored in the Product Session catalog and exposed by the admin API.
4. The Session history key must be cryptographically distinct from the protected-payload key. Startup environment validation and direct Control API construction both reject reuse.
5. Each Session derives a dedicated 32-byte AES key with HKDF-SHA256 using the Session ID as salt and fixed product-owned context information.
6. Every installed-SDK `SQLiteSession` item is stored as one exact AES-256-GCM envelope. The authenticated data binds schema version, Session ID, key ID and envelope version.
7. Plaintext items, unknown envelope fields or versions, malformed nonce/ciphertext, wrong key IDs, invalid authentication tags and invalid decrypted JSON fail closed. No corrupt item is skipped.
8. There is no history TTL. Session history does not disappear based on wall-clock time. Compaction remains disabled and is a later separately audited STEP.
9. Existing pre-STEP063 Session rows receive a nullable catalog column during schema migration, but they cannot resume without a recorded encryption key ID. They must be explicitly cleared and recreated.
10. Clear is intentionally possible without decrypting history so an operator can remove legacy, corrupt or wrong-key Session data. Active Turn clear remains forbidden.
11. Key validation applies at create, bind, acquire, active-Turn assertion, active item-count update and Turn release. Changing the configured key while a Turn is active cannot commit Session metadata.
12. Raw Session history remains absent from Product Events, Product/Evaluation databases and public API responses. The Runtime binding includes both the exact Session policy and encryption implementation SHA.
13. Redis, MongoDB, SQLAlchemy, Dapr, OpenAI-hosted Session, key rotation/migration, history export, compaction and TTL are not introduced by STEP063.
14. STEP063 Windows closure is `sh_run_step063_acceptance.cmd`. STEP064 must not be selected until its complete Windows result is reported and the packaged ZIP receives a fresh code audit.

## 21. MVP-core prioritization constitution after STEP066

1. Until the Agent Runtime MVP core is declared complete, select work that adds a user-visible Agent capability or is strictly required to make that capability executable.
2. Session key rotation, KMS/Vault integration, external Session backends, background health/reconnect management, distributed leasing, automated retention, and similar operations hardening are post-MVP tracks.
3. Already implemented hardening code may remain, but an unaccepted hardening STEP must not block the next core-capability STEP unless the core path directly depends on it.
4. The MVP core sequence after bounded orchestration and encrypted/compacted local Session is: remote MCP connectivity, hosted read-only search, multimodal document input, and a real bounded orchestration workflow.
5. Each MVP transport or hosted capability remains explicit, closed, allowlisted, read-only by default, and bound into the immutable Runtime fingerprint.
6. Do not expand an MVP transport foundation into health dashboards, reconnect loops, multi-server management, OAuth lifecycle, write approval, or distributed operations unless a later post-MVP plan explicitly selects that scope.

## 44. Multi-user server and service-client separation constitution after STEP069

1. `okcanvas-agent-runtime` is a multi-user server runtime, not a desktop or terminal application.
2. The current TUI, `/runner`, `/console`, and `clients/okcanvas-agent-cli` are development and acceptance-test harnesses only; they are not final service clients.
3. Final service clients are separate `agent-cli/`, `agent-web/`, and `agent-desktop/` applications that consume only documented server APIs, persisted SSE and verified Artifact contracts.
4. A service client must never import Runtime Python code or directly access Product SQLite, Session databases, workspaces, protected payloads, attachment stores, Artifact files or server secrets.
5. `/v1/service/**` is additive and tenant/principal scoped. Historical local-admin `/v1/**` routes remain development/acceptance surfaces and are not service-client compatibility promises.
6. Service Bearer tokens are external secrets. Only SHA-256 digests may appear in the configured registry; raw tokens must not be persisted in Product state, Events, Artifacts or evidence.
7. Attachment slots, Sessions, Submissions, Tasks, Runs and Approvals are bound to Product-owned resource ownership. Cross-principal and cross-tenant access returns 404 without disclosing existence.
8. Client idempotency is namespaced by tenant and principal before entering the existing global governed Submission boundary.
9. Approval operation is separated from submission ownership: only an `approval-operator` in the same tenant may inspect or decide an Approval.
10. Persisted SSE with cursor and `Last-Event-ID` is the service-client streaming contract. Process-local native SDK streaming is not exposed to remote clients.
11. Skill execution is not introduced by STEP069. `STEP070_PRODUCT_OWNED_SKILL_PACKAGE_FOUNDATION_V1` is selected next and must remain Product-owned, immutable, closed-registry and server-executed.
12. STEP070 must not begin before complete STEP069 Windows acceptance and a fresh audit of the packaged ZIP.

## 46. Product-owned Skill package constitution after STEP070

1. A Product Skill is a server-installed immutable package below `specs/skills/<skill-id>/`; it is not a client plugin, executable extension, Shell package, or dependency installer.
2. Skill V1 contains exactly one strict manifest, one bounded UTF-8 instruction file, and 1..8 declared bounded UTF-8 static resources. Symbolic paths, undeclared files, binary data, executable code and path escape are forbidden.
3. Every Skill has a manifest SHA, instructions SHA, resource SHA inventory and package SHA. Package identity and the Product Skill Runtime implementation SHA are part of the confirmation-bound Agent Runtime binding.
4. An Agent must explicitly declare `skills`; V1 allows at most one. Prompts, models, API callers and clients may not choose an undeclared Skill.
5. A Skill may require capabilities but may never add them. Required Function Tools, MCP servers, Hosted Tools, input mode, output contract and workspace mode must already be declared by the Agent.
6. Effective SDK instructions are a deterministic composition of immutable base Agent instructions, Skill instructions and declared static resources. No package filesystem path is provided to the model.
7. Service clients receive read-only Skill metadata and hashes through `/v1/service/skills`; Skill instructions and resource contents remain server-owned and are not client compatibility data.
8. The first package `document-review-v1` is bound only to `skill-document-review-agent` and declares no Tool, MCP, Hosted Tool, Session, child Agent, workspace, Shell, network or executable capability.
9. User uploads, ZIP/marketplace installation, arbitrary Python/JavaScript, Shell, dynamic dependencies, model-selected Skill discovery, client-side execution and mutable tenant Skill versions are prohibited in V1.
10. STEP070 is Windows-live accepted 30/30. STEP071 is selected only to prove the existing Skill through the actual governed service-client provider workflow.


## 47. Product Skill live workflow acceptance constitution after STEP071

1. STEP071 must not mutate `document-review-v1` version `1.0.0`; its package SHA remains the STEP070 identity.
2. The live acceptance uses only authenticated `/v1/service/**` contracts for metadata, attachment upload, governed Submission, confirmation, persisted Events and verified Artifacts.
3. `.env.local` is configuration data and must be parsed without execution. The API Key must never appear in source, logs, evidence, Product state or packaged files.
4. The current multimodal policy permits exactly `gpt-4.1`. A different or missing model fails before a provider call.
5. The fixture is one deterministic valid PDF containing explicit facts, one illegible field and instruction-looking document text. It is acceptance data, not Product runtime state.
6. Completion requires one successful real OpenAI model call, positive token usage, a valid `LocalDocumentReviewResult`, exact visible facts and unresolved approver handling.
7. No Function Tool, MCP, Hosted Tool, Handoff, Agent-as-Tool, Session, workspace, Shell, arbitrary network or executable Skill capability may appear.
8. Raw attachment bytes must remain absent from Product Events and Artifacts. Live evidence belongs only below ignored `docs/evidence/step071-live/**` and must not be packaged.
9. Deterministic acceptance cannot prove provider behavior. STEP071 remains Windows-live pending until the complete user-reported live JSON is received.
10. STEP072 must not be selected before STEP071 Windows live evidence and a fresh audit of the packaged ZIP.
11. The live review request must not disclose the fixture's expected reference, amount, date, decision, or unresolved field text; acceptance must prove extraction from the attachment rather than echo from the user request.
12. Exact provider HTTP request count must not be claimed without transport instrumentation. The authoritative invocation count is the persisted `model.started`/`model.completed` pair under the zero-retry route.

## 48. Windows Python launcher portability constitution after STEP072B

1. The binding incident analysis and launcher checklist is
   `docs/38-WINDOWS-PYTHON-LAUNCHER-PORTABILITY.md`; every Windows Python launcher change must read
   and preserve it.
2. Every current Windows Python launcher must start through
   `scripts/python_bytecode_isolation.py`. Configuration-bearing launchers must then route through
   `scripts/windows_entrypoint.py`; direct execution of a configured target script is prohibited.
3. `PYTHONPYCACHEPREFIX` must be set before child-interpreter startup, point outside the project, and
   be inherited by nested Python children. Adjacent project `.pyc` files are not trusted.
4. `.env.local` is parsed as data only by `windows_entrypoint.py`. It must never be called, sourced,
   executed, printed, passed as a command argument, or copied into Evidence.
5. Environment merging must preserve both allowlisted local configuration and inherited bytecode
   isolation. A wrapper that solves only one side of that composition is incomplete.
6. Tests that assert exact bytes, file size, hash, archive identity, or stale-bytecode behavior must
   use byte-exact writes such as `Path.write_bytes(text.encode("utf-8"))`; platform text newline
   translation must not influence a byte assertion.
7. Packaging must exclude `.env.local`, `.env.local.cmd`, `__pycache__`, `.pyc`, `.pyo`, virtual
   environments, raw live attachments, and ignored live Evidence.
8. A Windows launcher acceptance must prove the actual child interpreter sees the expected model and
   active external pycache prefix, while never exposing the API Key value. Loader startup messages
   alone are not acceptance evidence.
9. New or changed launchers require focused composition tests plus real Windows evidence. Failed
   evidence remains recorded after correction; do not overwrite the failure history.
10. STEP072B is Windows-live accepted from deterministic 24/24 and live 17/17 results with one
    `gpt-4.1` call, active external pycache isolation, successful `.env.local` forwarding, no provider
    trace diagnostic, no persisted API Key/raw attachment, and completed workspace cleanup.


## 49. Product-owned Sandbox Runtime foundation constitution after STEP073

1. Product Sandbox policy and provider identity are server-owned immutable specifications below
   `specs/sandbox/**`; prompts, models, Agent definitions, Skills and service clients cannot select a
   provider, image, host path, mount, network policy, capability or secret.
2. STEP073 is a contract-only foundation. Physical workspace materialization, Docker API calls,
   container lifecycle, network, ports, mounts, secrets, runtime image pull, resume, snapshots,
   Shell, Apply Patch and Skill materialization remain disabled.
3. The only active workspace mode is `none`. The names `sandbox-readonly-v1`, `sandbox-patch-v1` and
   `sandbox-shell-v1` are reserved declarations, not accepted capabilities.
4. SDK `SandboxAgent` defaults are forbidden. The retained 0.19.0 defaults include Filesystem,
   Shell and Compaction, and Filesystem includes Apply Patch. Every future SDK Sandbox construction
   must pass an explicit Product-approved capability list.
5. The retained SDK Docker client is not the Product policy authority. A future provider adapter must
   explicitly enforce immutable preinstalled image digest, no runtime pull, network none, no ports,
   no host/remote/Docker-socket mounts, non-root, cap-drop ALL, no-new-privileges, read-only root,
   quotas, bounded output, deletion and orphan reconciliation.
6. API keys, `.env.local`, service tokens and other Product secrets must never enter a Sandbox
   container or Sandbox manifest.
7. Sandbox policy SHA, provider contract SHA, foundation SHA and Product implementation SHA are part
   of every Agent Runtime binding. Any change invalidates prior governed confirmation.
8. `/v1/service/sandbox-runtime` is authenticated metadata only. It must not expose an image value,
   host path, Docker endpoint, credentials, executable content, workspace data or mutable config.
9. Reference source is audit evidence only. Product code must not import or execute
   `reference/upstream/**`.
10. STEP074 must not be selected before STEP073 deterministic and Windows acceptance are complete and
    the packaged ZIP receives a fresh code and Reference audit.

## 50. Product-owned hardened Docker lifecycle constitution after STEP074

1. STEP073 is Windows accepted 26/26. STEP074 may enable only the provider lifecycle; Agent Sandbox
   execution and every physical Agent workspace remain disabled.
2. Product Docker invocation uses an argument array with `shell=False`. Shell strings, batch
   interpolation and model-generated Docker arguments are forbidden.
3. A local tag is discovery input only. It must resolve through local `docker image inspect` to an
   immutable RepoDigest, and `docker container create` must use that digest with `--pull=never`.
4. Runtime image pull, build, import, registry access and automatic dependency installation are
   forbidden. Missing local images fail readiness without mutation.
5. Every created container must use network none, no published ports, no mounts, no Docker socket,
   read-only root, cap-drop ALL, no cap-add, no-new-privileges, fixed non-root UID/GID, bounded memory,
   CPU and PIDs, no restart and exact Product labels.
6. STEP074 runs the image default command only. It does not expose Shell, exec, Apply Patch,
   filesystem Tool, environment injection, secret injection, workspace materialization or model
   execution.
7. Effective inspect state must be verified before start. CLI flags alone are not acceptance proof.
8. Success requires exited/0, forced deletion including anonymous volumes, and a label-scoped orphan
   count of zero. Cleanup is attempted on every post-create failure.
9. The Docker CLI child environment must exclude OpenAI keys, Product encryption keys, model IDs and
   service configuration. No Product environment value enters the container.
10. `/v1/service/sandbox-runtime` may expose policy, limits and hashes but never an image value,
    host path, Docker endpoint, container ID, command output, credentials or mutable configuration.
11. The Docker lifecycle implementation SHA is part of every Agent Runtime binding even while all
    Agents remain `workspace_access=none`.
12. STEP075 must not be selected until STEP074 deterministic and Windows Docker acceptance are
    complete and the packaged ZIP receives a fresh source/Reference audit.

## STEP075 Product-owned read-only Sandbox workspace constitution

- Exactly one current Agent may use `workspace_access=sandbox-readonly-v1`:
  `sandbox-readonly-coding-agent` with Tool `sandbox_project_readonly_inspect`.
- All predecessor Agents remain `workspace_access=none`.
- Never use SDK `SandboxAgent` default capabilities, SDK `DockerSandboxClient`, host bind mounts,
  Docker socket mounts, container secrets, runtime image pull, network or exposed ports.
- Build a bounded canonical source snapshot; reject symlinks/path escapes and canonicalize accepted
  text to UTF-8 before hashing.
- Materialize only by streaming a Product-built deterministic tar archive to a fixed root `tar` process through `docker container exec --interactive --user 0:0`; host-path `docker cp` into tmpfs is forbidden. All model-visible read commands continue under the configured non-root user.
- Container commands are Product-owned argument arrays from the exact allowlist; never invoke a
  Shell parser and never accept model/user-selected executable or host path.
- Verify selected container-read bytes against snapshot SHA-256 entries before returning evidence.
- Persist only bounded identity/lifecycle evidence, never raw Tool input/result or workspace content.
- Force container deletion in `finally` and require label-scoped orphan count zero.
- Keep patching, Shell, process execution, dependency installation, Skill materialization, resume and
  remote/network providers disabled until an independently selected later STEP.

## Windows/Sandbox engineering issue recurrence constitution after STEP075A

1. A repeatable implementation, validation, Windows portability, packaging, or diagnostic failure must be recorded in `docs/issues/ISSUE_REGISTRY.md` and one detailed issue document.
2. The detailed issue must contain the exact symptom, code-confirmed root cause or explicitly bounded uncertainty, impact, fix, evidence, and automated recurrence gate.
3. A one-off patch does not close an issue. Code, evidence, Issue Registry status, and regression tests must agree.
4. Docker inspect values that are unordered or canonically normalized must be validated by security meaning, not raw serialization. Semantic validation must remain fail-closed for relaxed or unknown security values.
5. Sandbox Tool failures must emit a bounded stable code before SDK error normalization. Raw arguments, raw results, source content, host paths, image references, secrets, and exception text must not be persisted merely for diagnostics.
6. Acceptance workspace Product DB diagnostics use `databases/product.sqlite3`; documentation and scripts must not guess a singular `database/` directory.

## Docker command failure evidence constitution after STEP075B

1. Every Product-owned Docker CLI call must map to a closed stable operation identity; raw arguments are never diagnostic evidence.
2. Non-zero results must preserve the integer return code, bounded stderr category and output-truncation state.
3. The primary Docker failure remains authoritative through `finally`; removal or orphan-check failures must not silently replace it.
4. Post-failure evidence must state cleanup attempted/completed and orphan count when known.
5. Raw stdout/stderr, paths, image references, source content, exception messages and secrets remain forbidden in Events and handoff evidence.
6. A Docker root cause may not be claimed until the operation-level evidence supports it.

## Python subprocess stdin contract constitution after STEP075D

1. `subprocess.run(input=...)` owns and creates the stdin pipe. Product code must never pass `stdin=subprocess.PIPE` together with `input`.
2. Input-bearing calls pass `input` only; no-input calls pass `stdin=subprocess.DEVNULL` and no `input` keyword.
3. Mock subprocess tests are insufficient for stdin plumbing. Every adapter change requires at least one real child-process round-trip test.
4. Runner configuration errors must cross the Product boundary as a bounded stable `SandboxDockerError`; raw Python exception text, arguments, stdin bytes, source, paths, image references and secrets are not persisted.
5. A failure before process startup must not be attributed to Docker, image, tmpfs or tar without operation evidence.
6. STEP075D must preserve deterministic tar identity, the fixed root materializer, non-root model-visible reads, selected-file hash verification, cleanup/orphan reconciliation, network none and no Shell/Apply Patch.

## Exact evidence answer completeness constitution (STEP075F)

A schema-valid structured answer is not sufficient when the user explicitly requests an exact evidence-backed formula, signature, assignment, constant value, identifier, operator, or literal. The Product must validate the exact requested fragments against bounded Tool evidence before final Artifact registration. At most one correction model call is allowed, it must have no Tool/MCP/Handoff/filesystem/Shell/network/write capability, and it may not re-run the Sandbox Tool. Raw request, Tool evidence, draft and repair prompt must not be persisted in completeness lifecycle Events. Persistent incompleteness fails closed with `ANSWER_COMPLETENESS_FAILED` and must be recorded in the Engineering Issue Registry with automated recurrence gates.

## Product-owned deterministic evidence completion constitution (STEP075G)

When exact fragments have already been derived from one immutable, hash-verified Tool output, the Product must not spend another model call on mechanical completion. It may add only those derived fragments and their bounded repository-relative evidence references, remove evidence-backed paths from `unverified`, and re-run the same validator. It must add zero model calls, replay no Tool, persist no raw request/evidence/draft in completion Events, respect output-contract bounds and fail closed when exact requirements cannot be derived or remain incomplete. Model-based answer repair is disabled for this path.
