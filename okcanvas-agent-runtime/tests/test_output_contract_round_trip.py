from __future__ import annotations

from tests.artifact_test_support import artifact_service

from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog

import json
from pathlib import Path

import pytest

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import StoreReplenishmentReviewResult, UsageSummary
from okcanvas_agent_runtime.application.execution import GenericAgentExecutionService, GenericGatewayRunResult
from okcanvas_agent_runtime.application.execution.errors import GenericExecutionFailure
from okcanvas_agent_runtime.application.execution.output_registry import normalize_output, serialize_output
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


def test_business_output_survives_contract_specific_json_round_trip() -> None:
    output = StoreReplenishmentReviewResult.model_validate(EXPECTED)
    normalized = normalize_output("StoreReplenishmentReviewResult", output)
    payload = serialize_output("StoreReplenishmentReviewResult", normalized)
    assert isinstance(normalized, StoreReplenishmentReviewResult)
    assert payload["total_reorder_units"] == 19
    assert payload["recommendations"][0]["sku"] == "ergonomic-keyboard"


def test_constructed_empty_business_output_is_rejected() -> None:
    invalid = StoreReplenishmentReviewResult.model_construct()
    with pytest.raises(GenericExecutionFailure) as caught:
        serialize_output("StoreReplenishmentReviewResult", invalid)
    assert caught.value.code.value == "OUTPUT_CONTRACT_INVALID"


class InvalidConstructedGateway:
    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        return GenericGatewayRunResult(
            output=StoreReplenishmentReviewResult.model_construct(),
            usage=UsageSummary(),
            trace_id="trace_invalid",
            response_id="resp_invalid",
            sdk_version="0.19.0",
        )


def test_invalid_serialized_output_creates_no_artifact(tmp_path: Path) -> None:
    store = SQLiteProductStore(tmp_path / "product.sqlite3")
    store.initialize()
    service = GenericAgentExecutionService(
        runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
        definitions=AgentDefinitionCatalog(ROOT),
        store=store,
        gateway=InvalidConstructedGateway(),
        artifact_root=tmp_path / "artifacts",
        artifact_service=artifact_service(store, tmp_path / "artifacts"),
    )
    import asyncio

    envelope = asyncio.run(
        service.run(
            agent_definition_id="store-replenishment-review-agent",
            request='{"snapshot_id":"case001-shortage"}',
            settings=RuntimeSettings(model="test-model", api_key="secret"),
            live_opt_in=True,
        )
    )
    assert envelope.state == "FAILED"
    assert envelope.error is not None
    assert envelope.error.code.value == "OUTPUT_CONTRACT_INVALID"
    assert not list((tmp_path / "artifacts").rglob("final-output.json"))
