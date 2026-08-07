# STEP037A — Generic Function Tool Runtime code audit

## Status

`CODE_AUDITED_PLAN_COMPLETE_EXECUTABLE_BASELINE_UNCHANGED`

## Audited baseline

- executable STEP: `STEP037_INTERACTIVE_AGENT_RUNNER_FOUNDATION`
- version: `2.17.0`
- STEP037 Windows status: pending
- installed SDK contract: `openai-agents==0.19.0`

## Current product code findings

1. The repository already uses the official SDK Function Tool approval substrate for
   `local_text_metrics`; approval is not simulated.
2. Genericity is blocked by literal Tool-name and exact Tool-tuple checks in submission, Runtime
   binding, approval gateway/service, and tests.
3. The generic SDK execution gateway currently attaches no local Function Tools and treats every
   observed Tool lifecycle callback as MCP-only.
4. Tool policy exists in YAML but complete executable definition, input/output schemas, factory
   identity, and closed registry do not yet exist.
5. Runtime binding already hashes the current local Tool policy and implementation, but the private
   map is not a reusable Tool Runtime catalog.
6. Interactive Runner authority separation is already suitable: it may submit/observe, while the
   Approval Operator retains approve/reject authority.

## SDK reference findings

1. `FunctionTool` supports strict parameter JSON schema, typed output schema, ToolContext,
   approval, timeout, guardrails, enablement, namespaces, and caller policy.
2. V1 needs only strict schema, ToolContext, constant approval policy, and typed output; the other
   features are later tracks.
3. `function_tool` is the preferred factory and the SDK injects ToolContext only in the first
   parameter position.
4. Approval interruption/resume is owned by SDK RunState; product code should persist and govern it,
   not replace it.
5. Function Tool argument/output errors can be model-visible or raised; OKCanvas must define one
   explicit safe product policy rather than inherit accidental defaults.

## Architecture decision

Adopt:

- installed SDK `FunctionTool` / `function_tool`;
- strict JSON schema;
- ToolContext identity;
- native `needs_approval` interruption and RunState resume;
- safe lifecycle hooks.

Adapt:

- closed declarative Tool Runtime catalog;
- product-owned input/output contracts and factory composition;
- Runtime binding and confirmation fingerprint;
- canonical Events that omit arguments/results;
- existing approval ledger, encrypted RunState, and separate Approval Operator.

Reject in STEP038:

- dynamic Python import from Tool specs;
- arbitrary decorators discovered at runtime;
- mixed MCP/Function Tool Agents;
- multiple approval interruptions;
- Shell/hosted Tools;
- dynamic Tool Search;
- raw Tool argument/result persistence;
- approval controls in Interactive Runner.

## Required migration

`local_text_metrics` must move behind the new registry without changing its externally accepted
approve/reject behavior. A new read-only `local_text_fingerprint` Tool and Agent provide the second,
non-approval execution proof. Runtime binding changes invalidate pending Tool submissions; no silent
migration is allowed.

## Gate

No STEP038 executable code is authorized until `sh_run_step037_acceptance.cmd` passes on Windows.
