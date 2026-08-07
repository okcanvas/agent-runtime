from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, ConfigDict, Field


class StrictToolModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class FunctionToolApprovalMode(StrEnum):
    NEVER = "NEVER"
    ALWAYS = "ALWAYS"


class LocalTextExecutionInput(StrictToolModel):
    execution_id: str = Field(
        min_length=16,
        max_length=128,
        pattern=r"^execution_[a-f0-9]{16,96}$",
    )


class LocalTextFingerprintOutput(StrictToolModel):
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    utf8_bytes: int = Field(ge=0, le=1_000_000)
    characters: int = Field(ge=0, le=1_000_000)


class LocalTextMetricsOutput(LocalTextFingerprintOutput):
    words: int = Field(ge=0, le=1_000_000)
    lines: int = Field(ge=1, le=1_000_000)


class ProjectEvidenceOutput(StrictToolModel):
    path: str = Field(min_length=1, max_length=512)
    line_start: int = Field(ge=1, le=10_000_000)
    line_end: int = Field(ge=1, le=10_000_000)
    excerpt: str = Field(max_length=1_600)


class ProjectReadonlyInspectOutput(StrictToolModel):
    workspace_label: str = Field(min_length=1, max_length=128)
    snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    files_considered: int = Field(ge=1, le=3_000)
    bytes_considered: int = Field(ge=0, le=33_554_432)
    inspected_files: list[str] = Field(min_length=1, max_length=4)
    evidence: list[ProjectEvidenceOutput] = Field(min_length=1, max_length=4)
    evidence_characters: int = Field(ge=1, le=5_000)
    query_terms_considered: int = Field(ge=0, le=12)
    truncated: bool


class SandboxProjectReadonlyInspectOutput(ProjectReadonlyInspectOutput):
    workspace_access: str = Field(pattern=r"^sandbox-readonly-v1$")
    workspace_materialized: bool
    docker_call_count: int = Field(ge=1, le=64)
    selected_file_hashes_verified: bool
    cleanup_state: str = Field(pattern=r"^COMPLETED$")
    orphan_count: int = Field(ge=0, le=0)
    image_binding_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    network_mode: str = Field(pattern=r"^none$")
    shell_enabled: bool
    apply_patch_enabled: bool


ToolExecutor = Callable[[], Awaitable[dict[str, Any] | BaseModel]]


@dataclass(frozen=True)
class FunctionToolRuntime:
    schema_version: str
    runtime_version: str
    tool_id: str
    description: str
    sdk_kind: str
    factory_id: str
    approval_mode: FunctionToolApprovalMode
    strict_json_schema: bool
    read_only: bool
    filesystem_access: str
    network_access: str
    shell_access: str
    arguments_persisted: bool
    result_persisted_in_events: bool
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    definition_sha256: str
    policy_sha256: str
    input_schema_sha256: str
    output_schema_sha256: str
    implementation_sha256: str
    directory: Path

    def to_binding_dict(self) -> dict[str, str]:
        return {
            "tool_id": self.tool_id,
            "runtime_version": self.runtime_version,
            "definition_sha256": self.definition_sha256,
            "policy_sha256": self.policy_sha256,
            "input_schema_sha256": self.input_schema_sha256,
            "output_schema_sha256": self.output_schema_sha256,
            "implementation_sha256": self.implementation_sha256,
            "approval_mode": self.approval_mode.value,
            "sdk_kind": self.sdk_kind,
        }

    def to_public_dict(self) -> dict[str, object]:
        return {
            "tool_id": self.tool_id,
            "runtime_version": self.runtime_version,
            "approval_mode": self.approval_mode.value,
            "read_only": self.read_only,
            "filesystem_access": self.filesystem_access,
            "network_access": self.network_access,
            "shell_access": self.shell_access,
            "strict_json_schema": self.strict_json_schema,
        }
