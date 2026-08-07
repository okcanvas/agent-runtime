# STEP032 — Agent Output Contract Runtime Registry

STEP032 moves the active work back to the Agent Runtime core. It removes a business-domain dependency from the generic OpenAI Agents SDK gateway without expanding authority or introducing a new business Agent.

## Code-audited defect

Before STEP032, `execution/openai_gateway.py` imported `build_store_replenishment_result` and compared the literal output contract name `StoreReplenishmentReviewResult` twice. The generic gateway therefore knew which business domain owned recovery and would accumulate contract-name conditionals as more Agent output types were introduced.

## Runtime boundary

`execution/output_registry.py` now owns an explicit `OutputContractRuntime` for each supported output contract:

- Pydantic output type;
- optional invalid-final-output recovery function;
- optional recovery strategy identifier.

The generic gateway resolves one binding and only asks whether recovery is supported. It does not import replenishment code and does not compare business contract names.

Current bindings:

```text
CodingAgentResult
  output type: CodingAgentResult
  invalid-final-output recovery: disabled

StoreReplenishmentReviewResult
  output type: StoreReplenishmentReviewResult
  invalid-final-output recovery: enabled
  strategy: deterministic-invalid-final-output-fallback
```

This is not a generic automatic-fallback platform. A contract has no recovery unless product code explicitly registers one. The existing replenishment recovery is preserved at exactly its prior scope.

## SDK reference decision

Inspected:

- `reference/upstream/openai-agents-python-0.19.0/src/agents/agent_output.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/run_error_handlers.py`
- `reference/upstream/openai-agents-python-0.19.0/tests/test_invalid_final_output_handler.py`

Decisions:

- installed SDK `invalid_final_output` handler: ADOPT;
- product-owned contract registry around handler selection: ADAPT;
- fallback validation by SDK: ADOPT;
- fallback for every output contract: REJECT;
- second model turn or Tool replay: REJECT;
- direct import from `/reference`: REJECT.

## Deterministic acceptance

STEP032 runs three SDK-boundary scenarios with a deterministic fake SDK module:

1. valid `CodingAgentResult`: succeeds with no recovery handler;
2. invalid `CodingAgentResult`: fails as `SDK_RUN_FAILED`, no recovery event;
3. invalid `StoreReplenishmentReviewResult`: one deterministic recovery, total 19, one recovery event.

Every scenario uses one Runner invocation. No Tool or MCP event is allowed.
## Windows closure

The user-reported `sh_run_step032_acceptance` run passed all 19 checks with exactly two contracts, one Runner call per scenario, no Coding fallback, exact replenishment recovery to total 19, unchanged References, and cleanup `COMPLETED`. STEP032 is `WINDOWS_LIVE_ACCEPTED`.
