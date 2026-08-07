# STEP075G code audit

## Audited files

- `src/okcanvas_agent_runtime/execution/sandbox_answer_completeness.py`
- `src/okcanvas_agent_runtime/execution/openai_gateway.py`
- `src/okcanvas_agent_runtime/model.py`
- `tests/test_step075g_product_owned_deterministic_evidence_completion.py`
- `scripts/run_step075g_acceptance.py`
- `scripts/run_step075g_live_acceptance.py`

## Confirmed prior defect

STEP075F already passed the Sandbox Tool and had all required exact fragments in the typed in-memory Tool result. It nevertheless delegated mechanical answer completion to a new probabilistic model call. The Windows run recorded one repair start and completion but still failed the same deterministic validator. This is not missing evidence or a Docker defect.

## Implementation audit

`complete_sandbox_answer_from_evidence` accepts only:

- the schema-valid model draft;
- the typed Tool output recovered from exactly one Tool item;
- the validator assessment derived from that same evidence.

It does not parse a new request, invoke a model, execute a Tool, read the filesystem, access Docker or accept a path from the model. It inserts only `assessment.required_fragments` and line references from `tool_output.evidence` whose paths are already in the immutable evidence domain.

The gateway emits `agent.output.completion.started` and `agent.output.completion.completed`, both with `model_calls_added=0` and no raw request/evidence/draft persistence. The old correction Agent is absent from the active execution path.

## Fail-closed cases

- exact requirements cannot be derived;
- more than 20 exact fragments or evidence references;
- generated detail exceeds the output contract;
- the post-completion validator still reports an issue.

## Regression audit

The focused tests cover the exact STEP075F failure shape, exact fragment insertion, evidence-path cleanup, the 100-finding bound, no mutation of already complete results, one gateway `Runner.run` invocation, no model repair Events and fail-closed non-derivation.
