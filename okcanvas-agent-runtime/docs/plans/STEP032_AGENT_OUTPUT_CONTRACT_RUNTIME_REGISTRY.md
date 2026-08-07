# STEP032_AGENT_OUTPUT_CONTRACT_RUNTIME_REGISTRY

## Goal

Return the project focus to reusable Agent Runtime architecture by removing direct business-domain knowledge from the generic SDK gateway.

## Confirmed defect

`OpenAIGenericAgentGateway` directly imported the replenishment deterministic builder and selected recovery through literal `StoreReplenishmentReviewResult` comparisons. This made the runtime core domain-aware.

## Scope

- add a product-owned output-contract runtime registry;
- register output type and optional invalid-final-output recovery as one explicit binding;
- make the generic gateway consume only the resolved binding;
- preserve existing Coding and replenishment output behavior;
- prove that recovery remains disabled for CodingAgentResult;
- retain the official Agents SDK invalid-final-output boundary;
- add deterministic and Windows acceptance launchers;
- update handoff and packaging.

## Non-goals

- no new business Agent;
- no new commerce rule;
- no Tool, MCP, Handoff, Session, shell, or write authority;
- no automatic recovery for unknown contracts;
- no plugin marketplace or dynamic Python loading;
- no second model call;
- no direct `/reference` import.

## Acceptance

Require all checks true:

- exactly two registered output contracts;
- CodingAgentResult has no recovery;
- StoreReplenishmentReviewResult has the existing deterministic recovery;
- generic gateway contains no replenishment import or contract-name branch;
- valid coding output succeeds without a handler;
- invalid coding output fails without a recovery event;
- invalid replenishment output recovers to 12/7/0 and total 19;
- exact recovery strategy event;
- one Runner invocation per scenario;
- no Tool/MCP event;
- References unchanged;
- cleanup COMPLETED.

## Closure

STEP031 and STEP032 were both Windows live accepted on the user-reported 2026-07-30 runs. STEP033 was then selected only after the Runtime-centered code audit.
