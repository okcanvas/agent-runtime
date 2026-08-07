from __future__ import annotations

from pathlib import Path

import pytest

from okcanvas_agent_runtime.compatibility.source_contracts import read_component_source
from okcanvas_agent_runtime.core.contracts import (
    CodingAgentResult,
    GroupwareReadResult,
    OrganizationContextReadResult,
    HostedWebSearchResult,
    StoreReplenishmentReviewResult,
)
from okcanvas_agent_runtime.application.orchestration import BoundedOrchestrationResult
from okcanvas_agent_runtime.application.execution.contracts import GenericExecutionErrorCode
from okcanvas_agent_runtime.application.execution.errors import GenericExecutionFailure
from okcanvas_agent_runtime.application.execution.output_registry import (
    list_output_contracts,
    resolve_output_contract,
)

ROOT = Path(__file__).resolve().parents[1]


def test_registry_is_explicit_and_contract_specific() -> None:
    contracts = list_output_contracts()
    assert [item.contract_name for item in contracts] == [
        "BoundedOrchestrationResult",
        "CodingAgentResult",
        "GroupwareReadResult",
        "HostedWebSearchResult",
        "LocalDocumentReviewResult",
        "OrganizationAssistantResult",
        "OrganizationContextReadResult",
        "StoreReplenishmentReviewResult",
    ]
    orchestration = resolve_output_contract("BoundedOrchestrationResult")
    assert orchestration.output_type is BoundedOrchestrationResult
    assert orchestration.invalid_final_output_recovery is None
    assert orchestration.recovery_strategy is None
    coding = resolve_output_contract("CodingAgentResult")
    assert coding.output_type is CodingAgentResult
    assert coding.invalid_final_output_recovery is None
    assert coding.recovery_strategy is None

    groupware = resolve_output_contract("GroupwareReadResult")
    assert groupware.output_type is GroupwareReadResult
    assert groupware.invalid_final_output_recovery is None
    assert groupware.recovery_strategy is None

    hosted = resolve_output_contract("HostedWebSearchResult")
    assert hosted.output_type is HostedWebSearchResult
    assert hosted.invalid_final_output_recovery is None
    assert hosted.recovery_strategy is None

    organization_context = resolve_output_contract("OrganizationContextReadResult")
    assert organization_context.output_type is OrganizationContextReadResult
    assert organization_context.invalid_final_output_recovery is None
    assert organization_context.recovery_strategy is None
    assert organization_context.supports_nested_result_normalization is True
    assert organization_context.nested_normalization_strategy == (
        "product-owned-mcp-evidence-normalization-v1"
    )
    assert organization_context.runtime_version == "1.1.0"
    assert organization_context.implementation_id == "organization-context-read-result-runtime-v2"

    replenishment = resolve_output_contract("StoreReplenishmentReviewResult")
    assert replenishment.output_type is StoreReplenishmentReviewResult
    assert replenishment.invalid_final_output_recovery is not None
    assert replenishment.recovery_strategy == "deterministic-invalid-final-output-fallback"


def test_unknown_contract_fails_closed() -> None:
    with pytest.raises(GenericExecutionFailure) as captured:
        resolve_output_contract("UnknownResult")
    assert captured.value.code is GenericExecutionErrorCode.AGENT_DEFINITION_INVALID


def test_generic_gateway_has_no_business_contract_conditionals() -> None:
    source = read_component_source(ROOT, "execution.openai_gateway")
    assert "StoreReplenishment" not in source
    assert "build_store_replenishment_result" not in source
    assert "okcanvas_agent_runtime.verticals.store_replenishment" not in source
