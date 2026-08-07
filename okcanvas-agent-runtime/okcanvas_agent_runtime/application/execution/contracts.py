from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from okcanvas_agent_runtime.core.contracts import UsageSummary
from okcanvas_agent_runtime.domain.runs import EventSource
from okcanvas_agent_runtime.agent.tools.hosted_search import HostedWebSearchEvidence


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenericExecutionErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    LIVE_OPT_IN_REQUIRED = "LIVE_OPT_IN_REQUIRED"
    AGENT_DEFINITION_INVALID = "AGENT_DEFINITION_INVALID"
    AGENT_POLICY_DENIED = "AGENT_POLICY_DENIED"
    MCP_CONFIGURATION_INVALID = "MCP_CONFIGURATION_INVALID"
    MCP_CONNECTION_FAILED = "MCP_CONNECTION_FAILED"
    MCP_TOOL_POLICY_VIOLATION = "MCP_TOOL_POLICY_VIOLATION"
    HOSTED_SEARCH_POLICY_VIOLATION = "HOSTED_SEARCH_POLICY_VIOLATION"
    FUNCTION_TOOL_CONFIGURATION_INVALID = "FUNCTION_TOOL_CONFIGURATION_INVALID"
    FUNCTION_TOOL_POLICY_VIOLATION = "FUNCTION_TOOL_POLICY_VIOLATION"
    SDK_NOT_INSTALLED = "SDK_NOT_INSTALLED"
    SDK_VERSION_MISMATCH = "SDK_VERSION_MISMATCH"
    API_KEY_MISSING = "API_KEY_MISSING"
    MODEL_NOT_CONFIGURED = "MODEL_NOT_CONFIGURED"
    MODEL_ROUTE_DENIED = "MODEL_ROUTE_DENIED"
    SDK_RUN_FAILED = "SDK_RUN_FAILED"
    OUTPUT_CONTRACT_INVALID = "OUTPUT_CONTRACT_INVALID"
    ANSWER_COMPLETENESS_FAILED = "ANSWER_COMPLETENESS_FAILED"
    ARTIFACT_WRITE_FAILED = "ARTIFACT_WRITE_FAILED"
    PRODUCT_STATE_FAILED = "PRODUCT_STATE_FAILED"
    SESSION_BUSY = "SESSION_BUSY"
    SESSION_INTEGRITY_ERROR = "SESSION_INTEGRITY_ERROR"
    INPUT_GUARDRAIL_TRIPPED = "INPUT_GUARDRAIL_TRIPPED"
    OUTPUT_GUARDRAIL_TRIPPED = "OUTPUT_GUARDRAIL_TRIPPED"
    TOOL_INPUT_GUARDRAIL_TRIPPED = "TOOL_INPUT_GUARDRAIL_TRIPPED"
    TOOL_OUTPUT_GUARDRAIL_TRIPPED = "TOOL_OUTPUT_GUARDRAIL_TRIPPED"
    EXECUTION_CLAIM_LOST = "EXECUTION_CLAIM_LOST"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class GenericExecutionError(StrictModel):
    code: GenericExecutionErrorCode
    message: str
    retryable: bool = False
    detail_type: str | None = None


class GenericExecutionEnvelope(StrictModel):
    schema_version: Literal["okcanvas-generic-agent-execution-v1"] = (
        "okcanvas-generic-agent-execution-v1"
    )
    state: Literal["SUCCEEDED", "FAILED"]
    task_id: str | None = None
    run_id: str | None = None
    agent_definition_id: str
    agent_definition_version: str | None = None
    agent_definition_sha256: str | None = None
    model: str | None
    live_call: bool
    trace_id: str | None = None
    response_id: str | None = None
    artifact_id: str | None = None
    artifact_sha256: str | None = None
    usage: UsageSummary = Field(default_factory=UsageSummary)
    result: dict[str, Any] | None = None
    error: GenericExecutionError | None = None


@dataclass(frozen=True)
class GatewayLifecycleEvent:
    event_type: str
    payload: dict[str, Any]
    payload_schema_version: str = "okcanvas-agent-sdk-lifecycle-v1"
    source: EventSource = EventSource.AGENT_SDK


@dataclass(frozen=True)
class GenericGatewayRunResult:
    output: BaseModel
    usage: UsageSummary
    trace_id: str
    response_id: str | None
    sdk_version: str
    hosted_search_evidence: HostedWebSearchEvidence | None = None
