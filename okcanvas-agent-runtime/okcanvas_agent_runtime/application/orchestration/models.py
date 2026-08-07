from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, UsageSummary


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class BoundedOrchestrationPolicy:
    schema_version: str
    policy_id: str
    version: str
    child_count: int
    max_parallelism: int
    max_depth: int
    failure_mode: str
    cancellation_mode: str
    aggregation_mode: str
    child_output_contract: str
    root_output_contract: str
    child_session_mode: str
    read_only_language_only: bool
    native_child_streaming: bool
    workspace_access: str
    policy_sha256: str

    def to_binding_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "version": self.version,
            "child_count": self.child_count,
            "max_parallelism": self.max_parallelism,
            "max_depth": self.max_depth,
            "failure_mode": self.failure_mode,
            "cancellation_mode": self.cancellation_mode,
            "aggregation_mode": self.aggregation_mode,
            "child_output_contract": self.child_output_contract,
            "root_output_contract": self.root_output_contract,
            "child_session_mode": self.child_session_mode,
            "read_only_language_only": self.read_only_language_only,
            "native_child_streaming": self.native_child_streaming,
            "workspace_access": self.workspace_access,
            "policy_sha256": self.policy_sha256,
        }


class BoundedOrchestrationChildResult(StrictModel):
    ordinal: int = Field(ge=1, le=2)
    agent_definition_id: str = Field(min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9-]+$")
    state: Literal["SUCCEEDED"] = "SUCCEEDED"
    result: CodingAgentResult
    usage: UsageSummary


class BoundedOrchestrationResult(StrictModel):
    schema_version: Literal["okcanvas-bounded-orchestration-result-v1"] = (
        "okcanvas-bounded-orchestration-result-v1"
    )
    status: AgentStatus
    summary: str = Field(min_length=1, max_length=4000)
    child_count: int = Field(ge=2, le=2)
    children: list[BoundedOrchestrationChildResult] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def validate_deterministic_aggregate(self) -> "BoundedOrchestrationResult":
        if self.child_count != len(self.children):
            raise ValueError("child_count must equal children length")
        if [item.ordinal for item in self.children] != [1, 2]:
            raise ValueError("children must be ordered by declared ordinal")
        if len({item.agent_definition_id for item in self.children}) != 2:
            raise ValueError("orchestration child Agent IDs must be unique")
        severity = {AgentStatus.PASS: 0, AgentStatus.PARTIAL: 1, AgentStatus.FAIL: 2}
        expected_status = max(
            (item.result.status for item in self.children), key=lambda item: severity[item]
        )
        if self.status is not expected_status:
            raise ValueError("aggregate status must be the maximum child business severity")
        expected_summary = (
            f"{self.child_count}/{self.child_count} specialists completed; "
            f"aggregate status {self.status.value}."
        )
        if self.summary != expected_summary:
            raise ValueError("aggregate summary must use the deterministic product format")
        return self
