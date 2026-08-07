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
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.verticals.store_replenishment import build_store_replenishment_result
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import StoreReplenishmentReviewResult
from okcanvas_agent_runtime.application.execution import OpenAIGenericAgentGateway
from okcanvas_agent_runtime.application.execution import openai_gateway as gateway_module
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_runtime.adapters.openai.runtime import sdk_readiness

CASE_ROOT = (
    ROOT
    / "specs"
    / "business-cases"
    / "store-replenishment-review"
    / "case001-shortage"
)


def _run_fake_sdk(request: str) -> tuple[StoreReplenishmentReviewResult, list[object]]:
    events: list[object] = []
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    class FakeAgent:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeRunConfig:
        def __init__(self, **kwargs):
            self.values = kwargs

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
            assert max_turns == 1
            assert session is None
            assert error_handlers and "invalid_final_output" in error_handlers
            await hooks.on_agent_start(SimpleNamespace(), agent)
            await hooks.on_llm_start(SimpleNamespace(), agent, agent.instructions, [{"role": "user"}])
            await hooks.on_llm_end(
                SimpleNamespace(),
                agent,
                SimpleNamespace(response_id="resp_invalid", request_id="req", output=[1]),
            )
            output = error_handlers["invalid_final_output"](SimpleNamespace())
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
                last_response_id = "resp_invalid"

                def final_output_as(self, output_type, raise_if_incorrect_type=False):
                    assert output_type is StoreReplenishmentReviewResult
                    assert raise_if_incorrect_type is True
                    return output

            return Result()

    fake_agents.Agent = FakeAgent
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.gen_trace_id = lambda: "trace_recovered"
    fake_agents.set_default_openai_key = lambda _value: None

    async def sink(event):
        events.append(event)

    with (
        patch.dict(sys.modules, {"agents": fake_agents}),
        patch.object(sdk_readiness.importlib.metadata, "version", return_value="0.19.0"),
        patch.object(gateway_module.importlib.metadata, "version", return_value="0.19.0"),
    ):
        result = asyncio.run(
            OpenAIGenericAgentGateway().run(
                definition=AgentDefinitionCatalog(ROOT).resolve(
                    "store-replenishment-review-agent"
                ),
                request=request,
                run_id="run_step024b_acceptance",
                settings=RuntimeSettings(model="acceptance-model", api_key="redacted-secret"),
                lifecycle_sink=sink,
            )
        )
    return result.output, events


def run_acceptance(output: Path) -> int:
    request = json.dumps(
        json.loads((CASE_ROOT / "input.json").read_text(encoding="utf-8")),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    references_before = {
        item.reference_id: item.to_dict()
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    with AcceptanceWorkspace(step_id="STEP024B", output=output) as workspace:
        direct = build_store_replenishment_result(request)
        recovered, events = _run_fake_sdk(request)
        invalid = build_store_replenishment_result("not-json SECRET_SENTINEL")
        references_after = {
            item.reference_id: item.to_dict()
            for item in ReferenceCatalogService(ROOT).verify_all()
        }
        event_types = [getattr(item, "event_type", None) for item in events]
        checks = {
            "direct_formula_exact": direct.total_reorder_units == 19
            and [item.reorder_units for item in direct.recommendations] == [12, 7, 0],
            "sdk_invalid_output_recovered": recovered.total_reorder_units == 19,
            "recovery_event_recorded": "agent.output.recovered" in event_types,
            "model_output_not_persisted": all(
                getattr(item, "payload", {}).get("model_output_persisted") is not True
                for item in events
            ),
            "invalid_input_fail_closed": invalid.status.value == "INSUFFICIENT_DATA"
            and invalid.recommendations == [],
            "invalid_input_not_leaked": "SECRET_SENTINEL" not in invalid.model_dump_json(),
            "references_unchanged": references_before == references_after,
        }
        payload = {
            "schema_version": "okcanvas-step024b-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "total_reorder_units": recovered.total_reorder_units,
            "recommendations": [
                {"sku": item.sku, "reorder_units": item.reorder_units}
                for item in recovered.recommendations
            ],
            "event_types": event_types,
        }
        payload = workspace.finalize(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP024B_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
