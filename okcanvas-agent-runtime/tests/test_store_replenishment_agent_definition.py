from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.contracts import StoreReplenishmentReviewResult
from okcanvas_agent_runtime.application.execution.output_registry import resolve_output_type

ROOT = Path(__file__).resolve().parents[1]


def test_business_agent_definition_is_read_only_and_schema_bound() -> None:
    definition = AgentDefinitionCatalog(ROOT).resolve("store-replenishment-review-agent")
    assert definition.output_contract == "StoreReplenishmentReviewResult"
    assert definition.tools == ()
    assert definition.mcp_servers == ()
    assert definition.handoffs == ()
    assert definition.session_mode == "disabled"
    assert definition.max_turns == 1
    assert definition.output_schema == StoreReplenishmentReviewResult.model_json_schema()
    assert resolve_output_type(definition.output_contract) is StoreReplenishmentReviewResult


def test_case_pack_expected_output_satisfies_runtime_contract() -> None:
    expected = json.loads(
        (
            ROOT
            / "specs"
            / "business-cases"
            / "store-replenishment-review"
            / "case001-shortage"
            / "expected.json"
        ).read_text(encoding="utf-8")
    )
    result = StoreReplenishmentReviewResult.model_validate(expected)
    assert result.status.value == "ACTION_REQUIRED"
    assert result.total_reorder_units == 19
