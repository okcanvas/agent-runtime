from __future__ import annotations

import argparse
import asyncio
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import (
    AgentStatus,
    CodingAgentResult,
    StoreReplenishmentReviewResult,
)
from okcanvas_agent_runtime.application.execution import OpenAIGenericAgentGateway
from okcanvas_agent_runtime.application.execution import openai_gateway as gateway_module
from okcanvas_agent_runtime.application.execution.contracts import GenericExecutionErrorCode
from okcanvas_agent_runtime.application.execution.errors import GenericExecutionFailure
from okcanvas_agent_runtime.application.execution.output_registry import (
    list_output_contracts,
    resolve_output_contract,
)
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_runtime.adapters.openai.runtime import sdk_readiness

CASE_ROOT = (
    ROOT
    / "specs"
    / "business-cases"
    / "store-replenishment-review"
    / "case001-shortage"
)


class FakeModelBehaviorError(RuntimeError):
    pass


def _run_fake_sdk(
    *,
    agent_id: str,
    request: str,
    mode: str,
) -> tuple[object | None, GenericExecutionFailure | None, list[object], dict[str, object]]:
    events: list[object] = []
    captured: dict[str, object] = {"runner_calls": 0, "handler_present": None}
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["output_type"] = kwargs["output_type"]
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeRunConfig:
        def __init__(self, **kwargs):
            captured["run_config"] = kwargs

    class FakeRunHooks:
        pass

    class FakeRunner:
        @classmethod
        async def run(
            cls,
            agent,
            user_input,
            *,
            max_turns,
            hooks,
            run_config,
            error_handlers=None,
            session,
        ):
            captured["runner_calls"] = int(captured["runner_calls"]) + 1
            captured["handler_present"] = bool(
                error_handlers and "invalid_final_output" in error_handlers
            )
            assert session is None
            await hooks.on_agent_start(SimpleNamespace(), agent)
            await hooks.on_llm_start(
                SimpleNamespace(), agent, agent.instructions, [{"role": "user"}]
            )
            await hooks.on_llm_end(
                SimpleNamespace(),
                agent,
                SimpleNamespace(
                    response_id=f"resp_{mode}", request_id="req", output=[1]
                ),
            )
            if mode == "coding-invalid":
                assert error_handlers is None
                raise FakeModelBehaviorError("invalid coding final output")
            if mode == "coding-valid":
                assert error_handlers is None
                output = CodingAgentResult(
                    status=AgentStatus.PASS,
                    summary="Runtime contract registry kept the coding contract isolated.",
                    findings=[],
                    unverified=[],
                )
            elif mode == "replenishment-invalid":
                assert error_handlers is not None
                output = error_handlers["invalid_final_output"](SimpleNamespace())
                assert isinstance(output, StoreReplenishmentReviewResult)
            else:
                raise AssertionError(f"Unsupported fake SDK mode: {mode}")
            await hooks.on_agent_end(SimpleNamespace(), agent, output)
            usage = SimpleNamespace(
                requests=1,
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
                output_tokens_details=SimpleNamespace(reasoning_tokens=0),
            )

            class Result:
                context_wrapper = SimpleNamespace(usage=usage)
                last_response_id = f"resp_{mode}"

                def final_output_as(self, output_type, raise_if_incorrect_type=False):
                    assert output_type is type(output)
                    assert raise_if_incorrect_type is True
                    return output

            return Result()

    fake_agents.Agent = FakeAgent
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.gen_trace_id = lambda: f"trace_{mode}"
    fake_agents.set_default_openai_key = lambda _value: None

    async def sink(event):
        events.append(event)

    result = None
    failure = None
    with (
        patch.dict(sys.modules, {"agents": fake_agents}),
        patch.object(sdk_readiness.importlib.metadata, "version", return_value="0.19.0"),
        patch.object(gateway_module.importlib.metadata, "version", return_value="0.19.0"),
    ):
        try:
            result = asyncio.run(
                OpenAIGenericAgentGateway().run(
                    definition=AgentDefinitionCatalog(ROOT).resolve(agent_id),
                    request=request,
                    run_id=f"run_step032_{mode}",
                    settings=RuntimeSettings(
                        model="acceptance-model", api_key="redacted-secret"
                    ),
                    lifecycle_sink=sink,
                )
            )
        except GenericExecutionFailure as exc:
            failure = exc
    return result, failure, events, captured


def run_acceptance(output: Path) -> int:
    replenishment_request = json.dumps(
        json.loads((CASE_ROOT / "input.json").read_text(encoding="utf-8")),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    references_before = {
        item.reference_id: item.to_dict()
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    gateway_source = legacy_source_contract(
        ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py"
    ).read_text(encoding="utf-8")

    with AcceptanceWorkspace(step_id="STEP032", output=output) as workspace:
        contracts = list_output_contracts()
        coding_contract = resolve_output_contract("CodingAgentResult")
        replenishment_contract = resolve_output_contract(
            "StoreReplenishmentReviewResult"
        )
        coding_result, coding_failure, coding_events, coding_capture = _run_fake_sdk(
            agent_id="coding-agent",
            request="Inspect the supplied runtime contract boundary.",
            mode="coding-valid",
        )
        invalid_result, invalid_failure, invalid_events, invalid_capture = _run_fake_sdk(
            agent_id="coding-agent",
            request="Return an invalid structured output.",
            mode="coding-invalid",
        )
        recovered_result, recovered_failure, recovered_events, recovered_capture = (
            _run_fake_sdk(
                agent_id="store-replenishment-review-agent",
                request=replenishment_request,
                mode="replenishment-invalid",
            )
        )
        references_after = {
            item.reference_id: item.to_dict()
            for item in ReferenceCatalogService(ROOT).verify_all()
        }

        coding_event_types = [getattr(item, "event_type", None) for item in coding_events]
        invalid_event_types = [getattr(item, "event_type", None) for item in invalid_events]
        recovered_event_types = [
            getattr(item, "event_type", None) for item in recovered_events
        ]
        recovered_event = next(
            (
                item
                for item in recovered_events
                if getattr(item, "event_type", None) == "agent.output.recovered"
            ),
            None,
        )
        checks = {
            "two_runtime_output_contracts_registered": len(contracts) == 2,
            "coding_contract_type_exact": coding_contract.output_type is CodingAgentResult,
            "coding_contract_has_no_recovery": not coding_contract.supports_invalid_final_output_recovery
            and coding_contract.recovery_strategy is None,
            "replenishment_contract_type_exact": replenishment_contract.output_type
            is StoreReplenishmentReviewResult,
            "replenishment_recovery_registered": replenishment_contract.supports_invalid_final_output_recovery,
            "replenishment_recovery_strategy_exact": replenishment_contract.recovery_strategy
            == "deterministic-invalid-final-output-fallback",
            "generic_gateway_has_no_replenishment_domain_dependency": "StoreReplenishment"
            not in gateway_source
            and "build_store_replenishment_result" not in gateway_source
            and "okcanvas_agent_runtime.verticals.store_replenishment" not in gateway_source,
            "valid_coding_contract_succeeded": coding_failure is None
            and coding_result is not None
            and isinstance(coding_result.output, CodingAgentResult)
            and coding_result.output.status is AgentStatus.PASS,
            "coding_sdk_received_no_recovery_handler": coding_capture["handler_present"]
            is False,
            "invalid_coding_contract_failed": invalid_result is None
            and invalid_failure is not None,
            "invalid_coding_failure_contract_exact": invalid_failure is not None
            and invalid_failure.code is GenericExecutionErrorCode.SDK_RUN_FAILED
            and invalid_failure.retryable is True
            and invalid_failure.detail_type == "FakeModelBehaviorError",
            "invalid_coding_contract_not_recovered": "agent.output.recovered"
            not in invalid_event_types
            and invalid_capture["handler_present"] is False,
            "replenishment_contract_recovered": recovered_failure is None
            and recovered_result is not None
            and isinstance(recovered_result.output, StoreReplenishmentReviewResult),
            "replenishment_formula_exact": recovered_result is not None
            and recovered_result.output.total_reorder_units == 19
            and [item.reorder_units for item in recovered_result.output.recommendations]
            == [12, 7, 0],
            "recovery_event_strategy_exact": recovered_event is not None
            and getattr(recovered_event, "payload", {}).get("strategy")
            == "deterministic-invalid-final-output-fallback"
            and getattr(recovered_event, "payload", {}).get("model_output_persisted")
            is False,
            "recovery_scope_is_contract_specific": recovered_capture["handler_present"]
            is True
            and "agent.output.recovered" in recovered_event_types
            and "agent.output.recovered" not in coding_event_types,
            "one_model_turn_per_scenario": coding_capture["runner_calls"] == 1
            and invalid_capture["runner_calls"] == 1
            and recovered_capture["runner_calls"] == 1,
            "no_tool_or_mcp_events": all(
                not str(event_type).startswith("tool.")
                for event_type in (
                    coding_event_types + invalid_event_types + recovered_event_types
                )
            ),
            "references_unchanged": references_before == references_after,
        }
        payload = {
            "schema_version": "okcanvas-step032-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "contract_count": len(contracts),
            "contracts": [
                {
                    "contract_name": item.contract_name,
                    "output_type": item.output_type.__name__,
                    "invalid_final_output_recovery": item.supports_invalid_final_output_recovery,
                    "recovery_strategy": item.recovery_strategy,
                }
                for item in contracts
            ],
            "coding_valid": {
                "runner_calls": coding_capture["runner_calls"],
                "handler_present": coding_capture["handler_present"],
                "event_types": coding_event_types,
            },
            "coding_invalid": {
                "runner_calls": invalid_capture["runner_calls"],
                "handler_present": invalid_capture["handler_present"],
                "error_code": invalid_failure.code.value if invalid_failure else None,
                "detail_type": invalid_failure.detail_type if invalid_failure else None,
                "event_types": invalid_event_types,
            },
            "replenishment_invalid": {
                "runner_calls": recovered_capture["runner_calls"],
                "handler_present": recovered_capture["handler_present"],
                "total_reorder_units": (
                    recovered_result.output.total_reorder_units
                    if recovered_result is not None
                    else None
                ),
                "event_types": recovered_event_types,
            },
        }
        payload = workspace.finalize(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP032_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
