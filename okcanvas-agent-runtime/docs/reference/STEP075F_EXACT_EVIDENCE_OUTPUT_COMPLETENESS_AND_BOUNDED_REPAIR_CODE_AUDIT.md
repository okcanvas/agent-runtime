# STEP075F Code Audit

## Audited baseline

- STEP075E version `2.55.5`
- Windows live Run terminal status: `SUCCEEDED`
- Sandbox Tool completed once; model calls two
- workspace materialized; hashes verified; cleanup completed; orphan zero
- acceptance result: 32/33 because only `formula_observed` was false

## Exact product gap

The SDK returned a schema-valid `CodingAgentResult`. The Product validated only the output schema before registering the final Artifact. It did not compare the final answer with the bounded Tool evidence when the user explicitly requested an exact formula.

The draft replaced the exact evidence expression with `max(0, ...)`, omitted `SAFETY_STOCK = 12`, and marked the inspected evidence path as unverified. No remaining Docker, tar, subprocess, snapshot or hash-domain failure was present.

## Implementation

`execution/sandbox_answer_completeness.py` provides a pure bounded validator. It:

- recognizes explicit exactness requests;
- parses bounded Python evidence for matching function definitions;
- derives the complete return expression and referenced uppercase constant assignments;
- checks the serialized structured answer;
- rejects evidence-backed paths in `unverified`;
- builds an in-memory repair prompt from only the original request, bounded Tool output, structured draft and stable issue codes.

`OpenAIGenericAgentGateway` validates the first Sandbox answer before returning it to the Product execution service. If incomplete, it emits bounded lifecycle Events and invokes one separate correction Agent with:

- `tools=[]`;
- `mcp_servers=[]`;
- `handoffs=[]`;
- `max_turns=1`;
- `CodingAgentResult` output;
- no filesystem, Shell, network or write capability.

The original Sandbox Tool is never re-executed. The corrected answer is validated again. Persistent incompleteness raises `ANSWER_COMPLETENESS_FAILED` before final Artifact registration.

## Persisted evidence boundary

Persisted Events contain only booleans and counts such as exactness requested, complete, issue count, required-fragment count, evidence-path count, repair started/completed, maximum repair calls and Tool replay disabled.

The Events do not persist:

- the user request;
- bounded Tool evidence or source excerpts;
- the draft answer;
- the repair prompt;
- provider raw output;
- API keys or secrets.

## Security review

Unchanged Sandbox runtime boundary:

- already-local immutable image;
- network none, no ports or mounts;
- no container secrets;
- fixed root tar extractor only;
- fixed non-root read-only commands;
- selected-file hash verification;
- cleanup and orphan reconciliation.

The repair Agent has fewer capabilities than the original Sandbox Agent and cannot call the Tool again.

## Recurrence gates

`tests/test_step075f_sandbox_answer_completeness_and_bounded_repair.py` verifies:

- the exact STEP075E incomplete draft;
- exact formula and constant assignment derivation;
- evidence-backed path exclusion from `unverified`;
- complete answers skip repair;
- repair prompt is bounded and explicitly forbids Tool calls;
- exactly one typed Tool output is accepted;
- one repair model call maximum;
- repair Agent has zero Tools, MCP servers and Handoffs;
- Tool execution is not replayed;
- repair usage is aggregated.
