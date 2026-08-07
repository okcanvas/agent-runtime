# STEP038_GENERIC_FUNCTION_TOOL_RUNTIME_V1

Status: `IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`  
Version: `2.18.0`

## Purpose

Replace the one-off local Tool branching with one closed, product-owned Function Tool Runtime Registry while preserving the native OpenAI Agents SDK FunctionTool, ToolContext, needs_approval, and RunState boundaries.

## Implemented Runtime

The immutable Tool specification root is `specs/tools/<tool-id>/`. Every Tool is resolved through `FunctionToolRuntimeCatalog`; Agent definitions and model output cannot import Python factories or select implementation modules.

Each Tool binding includes:

- Tool ID and runtime version;
- definition and policy SHA-256;
- input/output JSON Schema SHA-256;
- implementation SHA-256;
- SDK kind;
- approval mode;
- execution-engine SHA through the Agent Runtime binding.

Exactly two P0 Tools are registered:

1. `local_text_fingerprint`
   - approval mode `NEVER`;
   - read-only and capability-free;
   - accepts only the opaque execution identity;
   - reads protected text from the product-owned execution closure;
   - returns SHA-256, UTF-8 bytes, and character count.
2. `local_text_metrics`
   - approval mode `ALWAYS`;
   - existing STEP020–STEP023 approval interruption/resume behavior;
   - migrated through the same Registry and SDK factory;
   - returns fingerprint plus word and line counts.

## Execution paths

- `generic-function-tool-execution-v1`: exactly one registered `NEVER` Tool, existing governed preflight/exact-confirmation/scheduler path.
- `governed-function-tool-approval-v1`: exactly one registered `ALWAYS` Tool, existing prepare/approve-or-reject/RunState path.

MCP and local Function Tools cannot be mixed in P0. Mixed approval modes, more than one generic Tool, multiple approval interruptions, Handoff, Session, and dynamic plugin loading fail closed.

## Persistence and privacy

Tool Events contain only Tool identity, runtime version, approval flag, call-ID presence, result presence, and false persistence flags. Raw Tool arguments, protected text, call IDs, and Tool results are not copied to Product Events. Protected payload lifecycle remains governed by the existing success/delete and failure/cancel retain policies.

## Evaluation closure

Both successful Tool modes have recorded-Run Evaluation cases. STEP038 also fixes an existing approval-run evidence inconsistency: `run.completed.usage` now records the same accumulated input/output/total Token counts stored on the Run, so the immutable recorded Evaluation can verify approval Runs.

## Deterministic acceptance

`docs/evidence/STEP038_ACCEPTANCE.json` passed 24/24:

- Registry count 2;
- read-only Tool executed once through existing governed confirmation;
- approve branch executed once and replay did not duplicate execution;
- reject branch executed zero times and replay was a no-op;
- two verified Artifacts and two PASSED recorded Evaluations;
- three Submission/Task/Run records, two Approval records;
- successful payloads deleted and rejected payload retained;
- raw request and Tool result absent from Product/Evaluation DB and Tool Events;
- References unchanged;
- cleanup `COMPLETED`.

## Explicitly deferred

- Native SDK streaming (`STEP039`);
- sub-Agent invocation scope (`STEP040`);
- Handoff (`STEP041`);
- Agent-as-Tool (`STEP042`);
- SQLite Session (`STEP043`);
- Guardrails (`STEP044`);
- Shell, hosted Tools, Tool Search, programmatic Tool calling, web/file search, code interpreter, computer use;
- mixed MCP/Function Tool Agents;
- approval decisions in Interactive Runner.

## Windows gate

Run `sh_setup.cmd`, then `sh_run_step038_acceptance.cmd`. Do not start STEP039 until all STEP038 checks pass on Windows.
