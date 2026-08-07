from __future__ import annotations

from tests.artifact_test_support import artifact_service
from tests.artifact_test_support import read_json_artifact

from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog

import asyncio
import json
from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import StoreReplenishmentReviewResult, UsageSummary
from okcanvas_agent_runtime.application.execution import (
    GatewayLifecycleEvent,
    GenericAgentExecutionService,
    GenericGatewayRunResult,
)
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = json.loads(
    (
        ROOT
        / "specs"
        / "business-cases"
        / "store-replenishment-review"
        / "case001-shortage"
        / "expected.json"
    ).read_text(encoding="utf-8")
)


class BusinessGateway:
    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        assert definition.output_contract == "StoreReplenishmentReviewResult"
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        await lifecycle_sink(GatewayLifecycleEvent("model.completed", {"response_id": "resp"}))
        await lifecycle_sink(GatewayLifecycleEvent("agent.completed", {"output_contract": definition.output_contract}))
        return GenericGatewayRunResult(
            output=StoreReplenishmentReviewResult.model_validate(EXPECTED),
            usage=UsageSummary(requests=1, input_tokens=10, output_tokens=10, total_tokens=20),
            trace_id="trace_business",
            response_id="resp",
            sdk_version="0.19.0",
        )


def test_generic_execution_supports_business_specific_output_contract(tmp_path: Path) -> None:
    store = SQLiteProductStore(tmp_path / "product.sqlite3")
    store.initialize()
    service = GenericAgentExecutionService(
        runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
        definitions=AgentDefinitionCatalog(ROOT),
        store=store,
        gateway=BusinessGateway(),
        artifact_root=tmp_path / "artifacts",
        artifact_service=artifact_service(store, tmp_path / "artifacts"),
    )
    envelope = asyncio.run(
        service.run(
            agent_definition_id="store-replenishment-review-agent",
            request='{"snapshot_id":"case001-shortage"}',
            settings=RuntimeSettings(model="test-model", api_key="secret"),
            live_opt_in=True,
        )
    )
    assert envelope.state == "SUCCEEDED"
    assert envelope.result is not None
    assert envelope.result["status"] == "ACTION_REQUIRED"
    artifact = store.verify_artifact(envelope.artifact_id)
    payload = read_json_artifact(store, tmp_path / "artifacts", envelope.artifact_id)
    assert payload["total_reorder_units"] == 19
