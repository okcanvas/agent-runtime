from __future__ import annotations

import hashlib
import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, TypeAdapter, ValidationError

from okcanvas_agent_runtime.verticals.store_replenishment import build_store_replenishment_result
from okcanvas_agent_runtime.core.contracts import (
    CodingAgentResult,
    GroupwareReadResult,
    HostedWebSearchResult,
    LocalDocumentReviewResult,
    OrganizationAssistantResult,
    OrganizationContextReadResult,
    StoreReplenishmentReviewResult,
)
from okcanvas_agent_runtime.application.orchestration import BoundedOrchestrationResult
from okcanvas_agent_runtime.application.execution.nested_output import NestedResultNormalization
from okcanvas_agent_runtime.application.organization_context.result_normalization import normalize_organization_context_nested_result
from okcanvas_agent_runtime.application.groupware_read.result_normalization import normalize_groupware_nested_result

from okcanvas_agent_runtime.application.execution.contracts import GenericExecutionErrorCode
from okcanvas_agent_runtime.application.execution.errors import GenericExecutionFailure

InvalidFinalOutputRecovery = Callable[[str], BaseModel]
NestedResultNormalizer = Callable[..., NestedResultNormalization]


@dataclass(frozen=True)
class OutputContractRuntime:
    """Product-owned runtime binding for one declared Agent output contract.

    The generic SDK gateway resolves this binding and remains unaware of business contract names,
    Pydantic model classes, and contract-specific recovery implementations.
    """

    contract_name: str
    output_type: type[BaseModel]
    invalid_final_output_recovery: InvalidFinalOutputRecovery | None = None
    recovery_strategy: str | None = None
    nested_result_normalizer: NestedResultNormalizer | None = None
    nested_normalization_strategy: str | None = None
    runtime_version: str = "1.0.0"
    implementation_id: str = ""
    definition_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        has_recovery = self.invalid_final_output_recovery is not None
        has_strategy = self.recovery_strategy is not None
        if has_recovery != has_strategy:
            raise ValueError(
                "invalid-final-output recovery and recovery strategy must be configured together"
            )
        if self.recovery_strategy is not None and not self.recovery_strategy.strip():
            raise ValueError("recovery strategy must be a non-empty string")
        has_nested_normalizer = self.nested_result_normalizer is not None
        has_nested_strategy = self.nested_normalization_strategy is not None
        if has_nested_normalizer != has_nested_strategy:
            raise ValueError(
                "nested-result normalizer and normalization strategy must be configured together"
            )
        if self.nested_normalization_strategy is not None and not self.nested_normalization_strategy.strip():
            raise ValueError("nested normalization strategy must be a non-empty string")
        if not self.runtime_version.strip() or not self.implementation_id.strip():
            raise ValueError("runtime version and implementation ID must be non-empty")
        schema = self.output_type.model_json_schema()
        output_module = importlib.import_module(self.output_type.__module__)
        output_path = Path(str(output_module.__file__)).resolve()
        recovery_module_sha256 = None
        if self.invalid_final_output_recovery is not None:
            recovery_module = importlib.import_module(
                self.invalid_final_output_recovery.__module__
            )
            recovery_path = Path(str(recovery_module.__file__)).resolve()
            recovery_module_sha256 = hashlib.sha256(recovery_path.read_bytes()).hexdigest()
        nested_normalizer_module_sha256 = None
        if self.nested_result_normalizer is not None:
            nested_module = importlib.import_module(self.nested_result_normalizer.__module__)
            nested_path = Path(str(nested_module.__file__)).resolve()
            nested_normalizer_module_sha256 = hashlib.sha256(nested_path.read_bytes()).hexdigest()
        canonical = {
            "schema_version": "okcanvas-output-contract-runtime-v1",
            "contract_name": self.contract_name,
            "runtime_version": self.runtime_version,
            "implementation_id": self.implementation_id,
            "output_type": f"{self.output_type.__module__}.{self.output_type.__qualname__}",
            "output_schema_sha256": hashlib.sha256(
                json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "output_module_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
            "recovery_enabled": has_recovery,
            "recovery_strategy": self.recovery_strategy,
            "recovery_module_sha256": recovery_module_sha256,
            "nested_normalization_enabled": has_nested_normalizer,
            "nested_normalization_strategy": self.nested_normalization_strategy,
            "nested_normalizer_module_sha256": nested_normalizer_module_sha256,
        }
        object.__setattr__(
            self,
            "definition_sha256",
            hashlib.sha256(
                json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        )

    def to_fingerprint_dict(self) -> dict[str, object]:
        return {
            "contract_name": self.contract_name,
            "runtime_version": self.runtime_version,
            "implementation_id": self.implementation_id,
            "recovery_strategy": self.recovery_strategy,
            "nested_normalization_strategy": self.nested_normalization_strategy,
            "definition_sha256": self.definition_sha256,
        }

    @property
    def supports_invalid_final_output_recovery(self) -> bool:
        return self.invalid_final_output_recovery is not None

    @property
    def supports_nested_result_normalization(self) -> bool:
        return self.nested_result_normalizer is not None

    def normalize_nested_result(
        self, *, result: Any, output: BaseModel, request: str
    ) -> NestedResultNormalization:
        normalizer = self.nested_result_normalizer
        if normalizer is None:
            return NestedResultNormalization(output=output, metadata={})
        normalized = normalizer(result=result, output=output, request=request)
        if not isinstance(normalized.output, self.output_type):
            raise TypeError(
                f"Nested normalizer for {self.contract_name} returned "
                f"{type(normalized.output).__name__}"
            )
        return normalized

    def recover_invalid_final_output(self, request: str) -> BaseModel:
        recovery = self.invalid_final_output_recovery
        if recovery is None:
            raise RuntimeError(
                f"Output contract does not support invalid-final-output recovery: {self.contract_name}"
            )
        recovered = recovery(request)
        if not isinstance(recovered, self.output_type):
            raise TypeError(
                f"Recovery for {self.contract_name} returned {type(recovered).__name__}"
            )
        return recovered


_OUTPUT_CONTRACTS: dict[str, OutputContractRuntime] = {
    "CodingAgentResult": OutputContractRuntime(
        contract_name="CodingAgentResult",
        output_type=CodingAgentResult,
        implementation_id="coding-agent-result-runtime-v1",
    ),
    "BoundedOrchestrationResult": OutputContractRuntime(
        contract_name="BoundedOrchestrationResult",
        output_type=BoundedOrchestrationResult,
        implementation_id="bounded-orchestration-result-runtime-v1",
    ),
    "GroupwareReadResult": OutputContractRuntime(
        contract_name="GroupwareReadResult",
        output_type=GroupwareReadResult,
        nested_result_normalizer=normalize_groupware_nested_result,
        nested_normalization_strategy="product-owned-cross-domain-mcp-evidence-normalization-v1",
        runtime_version="1.1.0",
        implementation_id="groupware-read-result-runtime-v2",
    ),
    "HostedWebSearchResult": OutputContractRuntime(
        contract_name="HostedWebSearchResult",
        output_type=HostedWebSearchResult,
        implementation_id="hosted-web-search-result-runtime-v1",
    ),
    "LocalDocumentReviewResult": OutputContractRuntime(
        contract_name="LocalDocumentReviewResult",
        output_type=LocalDocumentReviewResult,
        implementation_id="local-document-review-result-runtime-v1",
    ),
    "OrganizationContextReadResult": OutputContractRuntime(
        contract_name="OrganizationContextReadResult",
        output_type=OrganizationContextReadResult,
        nested_result_normalizer=normalize_organization_context_nested_result,
        nested_normalization_strategy="product-owned-mcp-evidence-normalization-v1",
        runtime_version="1.1.0",
        implementation_id="organization-context-read-result-runtime-v2",
    ),
    "OrganizationAssistantResult": OutputContractRuntime(
        contract_name="OrganizationAssistantResult",
        output_type=OrganizationAssistantResult,
        implementation_id="organization-assistant-result-runtime-v1",
    ),
    "StoreReplenishmentReviewResult": OutputContractRuntime(
        contract_name="StoreReplenishmentReviewResult",
        output_type=StoreReplenishmentReviewResult,
        invalid_final_output_recovery=build_store_replenishment_result,
        recovery_strategy="deterministic-invalid-final-output-fallback",
        implementation_id="store-replenishment-result-runtime-v1",
    ),
}


def list_output_contracts() -> tuple[OutputContractRuntime, ...]:
    return tuple(_OUTPUT_CONTRACTS[name] for name in sorted(_OUTPUT_CONTRACTS))


def resolve_output_contract(contract_name: str) -> OutputContractRuntime:
    contract = _OUTPUT_CONTRACTS.get(contract_name)
    if contract is None:
        raise GenericExecutionFailure(
            GenericExecutionErrorCode.AGENT_DEFINITION_INVALID,
            f"Unsupported output contract: {contract_name}",
        )
    return contract


def validate_output_schema(contract_name: str, schema: dict[str, object]) -> type[Any]:
    contract = resolve_output_contract(contract_name)
    expected = contract.output_type.model_json_schema()
    if schema != expected:
        raise GenericExecutionFailure(
            GenericExecutionErrorCode.AGENT_DEFINITION_INVALID,
            f"Output schema does not match runtime contract: {contract_name}",
        )
    return contract.output_type


def resolve_output_type(contract_name: str) -> type[Any]:
    return resolve_output_contract(contract_name).output_type


def normalize_output(contract_name: str, output: Any) -> BaseModel:
    """Force a contract-specific JSON round trip before product persistence.

    This deliberately does not trust ``BaseModel.model_dump()`` alone. The SDK guarantees the
    configured output type, while the product boundary independently verifies that the serialized
    JSON still satisfies the same contract before an Artifact can be created.
    """

    output_type = resolve_output_contract(contract_name).output_type
    adapter = TypeAdapter(output_type)
    try:
        dumped = adapter.dump_python(output, mode="json", round_trip=True)
        encoded = json.dumps(dumped, ensure_ascii=False, separators=(",", ":"))
        validated = adapter.validate_json(encoded)
    except (TypeError, ValueError, ValidationError) as exc:
        raise GenericExecutionFailure(
            GenericExecutionErrorCode.OUTPUT_CONTRACT_INVALID,
            f"Agent output did not survive the {contract_name} JSON round trip",
            detail_type=type(exc).__name__,
        ) from exc
    if not isinstance(validated, BaseModel):
        raise GenericExecutionFailure(
            GenericExecutionErrorCode.OUTPUT_CONTRACT_INVALID,
            f"Agent output is not a Pydantic model for {contract_name}",
            detail_type=type(validated).__name__,
        )
    return validated


def serialize_output(contract_name: str, output: Any) -> dict[str, Any]:
    normalized = normalize_output(contract_name, output)
    payload = normalized.model_dump(mode="json", round_trip=True)
    if not isinstance(payload, dict) or not payload:
        raise GenericExecutionFailure(
            GenericExecutionErrorCode.OUTPUT_CONTRACT_INVALID,
            f"Agent output serialized to an empty or non-object payload for {contract_name}",
            detail_type=type(payload).__name__,
        )
    return payload
