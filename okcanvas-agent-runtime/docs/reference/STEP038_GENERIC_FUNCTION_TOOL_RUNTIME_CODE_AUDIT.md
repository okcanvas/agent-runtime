# STEP038 — Generic Function Tool Runtime code audit

## Confirmed pre-STEP038 condition

The approval path and RunState mechanics were product-grade, but the Runtime selected `local_text_metrics` through literal product branching. The generic OpenAI gateway rejected every local Tool, and Tool definition/policy/schema/implementation did not share one closed Registry contract.

## Upstream boundaries inspected

From retained `openai-agents-python-0.19.0`:

- SDK `FunctionTool` and `function_tool` construction;
- strict JSON schema handling;
- `ToolContext` for invocation identity;
- `needs_approval` and RunState interruption/resume;
- Function Tool tests covering schema, context, approval, and result validation.

Adopted: installed SDK primitives and native approval state.  
Adapted: immutable product specs, Registry, protected-payload executor closure, Runtime binding, safe canonical Events, Product Artifact/Evaluation.  
Rejected: dynamic imports, model-selected factories, raw argument/result Event persistence, generic unrestricted plugin loading.

## Code changes

- `function_tools/`: models, implementations, factories, catalog, errors.
- `specs/tools/`: immutable definitions, policies, schemas, documentation.
- `agent_definitions/`: registered Tool resolution and public capability metadata.
- `run_submission/`: execution mode selected from registered approval mode.
- `execution/openai_gateway.py`: one non-approval Function Tool through native SDK factory.
- `execution/service.py`: generic validation permits only the registered non-approval P0 path.
- `execution/runtime_binding.py`: Tool contract and execution path bound to confirmation fingerprint.
- `tool_approval/`: existing native interruption/resume generalized through Registry.
- `interactive_runner`: capability chips expose Tool ID and approval mode; no approval decision added.
- `evaluation`: success cases for both Tool modes.

## Additional confirmed defect fixed

Approval preparation and resume Token counts were accumulated on the Product Run, but the completion Event contained only resume usage. Recorded Evaluation correctly rejected that inconsistency. STEP038 now emits accumulated input/output/total Token counts in the completion Event.

## Scope decision

This is a Function Tool skeleton, not a general Tool platform. Exactly two deterministic, read-only, capability-free Tools prove both approval modes. Wider Tools are deferred until streaming and sub-Agent foundations are in place.
