# OR-ISSUE-025 — Compatibility monkeypatch surface did not forward to the concrete Adapter

## Status

```text
FIX_IMPLEMENTED_DETERMINISTIC_AND_FRESH_ZIP_ACCEPTED_WINDOWS_PENDING
STEP: STEP081_ROOT_PACKAGE_AND_ARCHITECTURE_RESTRUCTURING
```

## Exact symptom

`test_step023a_live_sdk_resume_turn_budget.py` monkeypatched `application.approvals.gateway.build_sdk_function_tool`, but the symbol no longer existed after the concrete OpenAI approval gateway moved to `adapters/openai/local_tool_approval.py`. The test failed before exercising the two-turn interruption/resume budget.

## Code-confirmed root cause

The public `OpenAILocalToolApprovalGateway` class was preserved through a lazy compatibility export, but its historical module-level monkeypatch seam was not. The concrete Adapter imported `build_sdk_function_tool` directly from the Agent Tool package at module import time, bypassing any patch applied to the historical gateway module.

## Impact

Historical deterministic tests and downstream integrations that replace the SDK Tool factory could not isolate OpenAI SDK execution. A structurally compatible class import therefore did not preserve the complete behavioral test seam.

## Fix

- restored a lazy `build_sdk_function_tool` forwarding function in the Application gateway compatibility module;
- changed the concrete Adapter to resolve the factory through that forwarding surface at call time;
- retained static Application-to-Adapter dependency prohibition.

## Detailed evidence

The STEP023A live SDK interruption/resume budget regression passes after the forwarding seam is restored.

## Recurrence-prevention gate

`tests/test_step023a_live_sdk_resume_turn_budget.py::test_live_sdk_prepare_budget_covers_interruption_and_resume` monkeypatches the historical module and proves that the concrete Adapter uses the patched factory.
