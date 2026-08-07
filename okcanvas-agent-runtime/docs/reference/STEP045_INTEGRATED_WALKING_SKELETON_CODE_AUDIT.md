# STEP045 Integrated Walking Skeleton Code Audit

## Audit conclusion

The P0 primitive implementations already exist and are independently accepted. The missing product boundary was not another SDK abstraction; it was a closed, visible and code-verifiable integration surface. Prior to STEP045, the Runner could choose Agents but had no authoritative scenario matrix and did not show the Product invocation graph.

## Existing executable paths reused

- governed boundary: `src/okcanvas_agent_runtime/run_submission/**`;
- Product execution and Artifact: `src/okcanvas_agent_runtime/execution/**`;
- Interactive Runner: `src/okcanvas_agent_runtime/interactive_runner/**`;
- Function Tool and approval: `function_tools/**`, `tool_approval/**`;
- MCP: `mcp_definitions/**`, `mcp_clients/**`;
- streaming: `streaming/**`;
- invocation ledger: `invocations/**`;
- Handoff: `handoffs/**`;
- Agent-as-Tool: `agent_tools/**`;
- Session: `sessions/**`;
- Guardrail: `guardrails/**`;
- Evaluation: `evaluation/**`.

STEP045 does not fork these paths.

## Reference findings retained

The Reference-wide audit established that routing is a Handoff pattern, Agent-as-Tool is nested Function Tool execution, parallelization is application orchestration, Session is passed into the SDK Runner and native stream events are distinct from durable Product evidence. STEP037–044 implemented these boundaries. STEP045 therefore integrates accepted product adapters rather than importing or reproducing Reference examples.

Applicable immutable paths include:

- `reference/upstream/openai-agents-python-0.19.0/examples/basic/**`;
- `examples/agent_patterns/routing.py` and `agents_as_tools.py`;
- `examples/agent_patterns/parallelization.py` as deferred orchestration evidence;
- `examples/memory/**` and Session tests;
- `examples/mcp/**`;
- `tests/test_stream_input_guardrail_timing.py` and Guardrail tests;
- SDK streaming and Handoff tests under `reference/upstream/openai-agents-python-0.19.0/tests/**`.

Executable source still has zero direct `/reference` imports.

## Chosen implementation

A product-owned immutable JSON catalog is loaded by `WalkingSkeletonScenarioCatalog`. The loader rejects missing/symlinked/path-escaped files, unknown fields, wrong scenario count/order, duplicate values, invalid action modes, non-`none` P0 workspace access and malformed Session templates.

The authenticated Control API validates that every scenario Agent and Evaluation case exists. The Runner fetches this catalog, renders ten selectable cards and fills the normal governed request form. It also reads `/v1/runs/{run_id}/invocations` to make ROOT/child identities visible.

## Acceptance integrity

The release matrix invokes prior deterministic acceptance scripts only from the STEP045 acceptance harness using fresh isolated acceptance workspaces. Runtime code contains no subprocess call, script lookup or alternate execution route. The matrix is intentionally compositional: it proves that each independently accepted primitive still works in the same packaged baseline while the Runner presents all of them coherently.

## Deferred finding

P0 scenarios remain mostly capability-isolated. The next work must not infer that arbitrary combinations are safe. Composition needs separate policy and failure analysis, especially Session+approval, Session+child Agent, multiple child invocations, physical workspace, external side effects and parallel execution.
