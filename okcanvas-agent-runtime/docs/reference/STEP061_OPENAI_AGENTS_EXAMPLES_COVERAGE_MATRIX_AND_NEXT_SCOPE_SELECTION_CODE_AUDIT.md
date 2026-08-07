# STEP061 Code Audit — OpenAI Agents SDK Examples Coverage and Next Scope

## Accepted predecessor

STEP060 is closed from the user's Windows evidence:

- deterministic acceptance: `20/20`;
- cleanup: `COMPLETED` exactly once;
- final Task/Run/Submission/Invocation/Event/Artifact/Evaluation counts: `1/1/1/1/12/1/0`;
- protected payload files: `0`;
- fixture evidence: one file and `608` characters;
- real OpenAI Artifact: `PASS`;
- real implementation evidence: `src/okcanvas_agent_runtime/control_api/app.py:485-487`;
- unrelated findings: none;
- total usage: `2,688`, below the `5,000` token gate.

The accepted evidence is recorded in
`docs/evidence/STEP060_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`. It is user-reported operational
evidence, not a container-executed OpenAI call.

## Exact SDK example inventory

The immutable tree
`reference/upstream/openai-agents-python-0.19.0/examples` contains **216** Python files.
Four root runner/support files are not capability examples:

- `__init__.py`;
- `auto_mode.py`;
- `run_examples.py`;
- `web_search_utils.py`.

The resulting capability inventory is therefore **212 files across 15 top-level areas**. Every
classified file is recorded with SHA-256, line count, observed SDK imports, decision, target track,
and current product evidence in
`docs/reference/STEP061_OPENAI_AGENTS_EXAMPLES_COVERAGE_MATRIX.json`.

## Current Runtime facts confirmed from code

### Child Agent execution is bounded to one edge, not orchestration

`src/okcanvas_agent_runtime/model.py` declares:

- native Handoff maximum per Run: `1`;
- Agent-as-Tool maximum per Run: `1`;
- Session Handoff depth: `1`;
- Session Agent-as-Tool depth: `1`.

`src/okcanvas_agent_runtime/execution/openai_gateway.py` rejects definitions that do not contain
exactly one declared Handoff target or exactly one declared Agent-as-Tool target for those paths.
The product code contains no sibling Agent fan-out, no orchestration TaskGroup/gather path, no
partial-failure aggregation contract, and no sibling cancellation policy.

The existing invocation ledger is still useful: it already owns root/child identity, parent
relationships, state, token usage, and Runtime binding. STEP062 can extend that ledger instead of
inventing an unrelated workflow engine.

### Session hardening is explicitly disabled

`src/okcanvas_agent_runtime/sessions/policy.py` rejects history truncation, compaction, and Session
encryption. `RuntimeInfo` reports the installed SDK SQLite backend with history encryption and
compaction both false. Remote Session backends are not imported by product code.

### MCP is intentionally narrow

`src/okcanvas_agent_runtime/mcp_clients/openai_factory.py` imports only `MCPServerStdio`,
`MCPServerManager`, and `create_static_tool_filter`. It configures static allowed Tool names,
`require_approval="never"`, `strict=True`, and `connect_in_parallel=False`. Product code does not
import Streamable HTTP, SSE, Hosted MCP, MCP prompts/resources, or dynamic Tool filtering.

### Model route is OpenAI Responses only

`RuntimeInfo` fixes provider `openai`, API `responses`, transport `http`, official base URL, no
provider prefixes, no automatic fallback, and zero Runner/provider retries. Product code does not
import LiteLLM, AnyLLM, or a custom `ModelProvider` implementation.

### Hosted tools, multimodal input, realtime, voice, and Sandbox are absent

Product source contains no imports of `WebSearchTool`, `FileSearchTool`, `CodeInterpreterTool`,
`ComputerTool`, `ImageGenerationTool`, `ToolSearchTool`, `ProgrammaticToolCallingTool`,
`RealtimeAgent`, `VoicePipeline`, `SandboxAgent`, or `Manifest`.

The current submission and Node CLI paths are text-only. The retained Codex disposable workspace
path is not the SDK Sandbox framework.

## File-level decisions

The exact matrix contains:

- **ADOPT: 16** — direct current SDK primitive wiring;
- **ADAPT: 16** — narrower product-owned representation;
- **DEFER: 171** — legitimate but absent capability or separate track;
- **REJECT: 9** — explicit conflict with current constitution.

The main rejection decisions are:

- hosted multi-agent beta, because it can bypass the Product invocation ledger;
- non-strict output, because verified structured Artifacts are authoritative;
- `previous_response_id`, because response storage and provider IDs are disabled and SQLite Session
  is the continuity authority;
- positive retry examples, because Runner and provider retries are fixed at zero;
- reasoning-content examples, because reasoning content, summaries, item IDs, and provider data are
  deliberately neither requested nor persisted.

## Next implementation selection

The first implementation candidate is
`STEP062_BOUNDED_MULTI_AGENT_ORCHESTRATION_FOUNDATION`.

The selection is based on the exact files:

- `examples/agent_patterns/parallelization.py` — concurrent sibling Agent execution;
- `examples/agent_patterns/deterministic.py` — product-owned deterministic sequencing;
- `examples/financial_research_agent/manager.py` — planner/search/verifier/writer manager flow;
- `examples/research_bot/manager.py` — bounded research manager flow;
- `examples/agent_patterns/llm_as_a_judge.py` — optional non-authoritative quality signal.

STEP062 must not copy those demos as an application. It must add a product-owned, closed,
Runtime-bound orchestration definition and preserve the existing Task/Run/Event/Artifact and child
Invocation authorities.

## STEP062 minimum design boundary

The first slice should prove exactly one closed orchestration graph:

```text
root manager
→ two read-only sibling specialists in parallel
→ deterministic product-owned aggregation
→ one verified root Artifact
```

Required policy:

- fixed child Agent IDs and maximum sibling count;
- maximum depth `1` for V1;
- independent child invocation records under the same Product Run;
- aggregate token and duration budgets;
- explicit fail-fast versus collect-partial policy;
- cancellation request and terminal state for unfinished siblings;
- deterministic aggregation outside the model;
- no child Product Run, no writable workspace, no MCP/network expansion, no Session, no approval,
  and no LLM judge as authority.

A later orchestration STEP may add planner-generated work items, verifier/writer stages, or optional
non-authoritative model judging only after V1 closure.
