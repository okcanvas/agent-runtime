from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from okcanvas_agent_runtime.domain.invocations.models import AgentInvocationRecord, InvocationKind, InvocationState, WorkspaceAccess
from typing import Any


class TaskStatus(StrEnum):
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RunStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    INTERRUPTED = "INTERRUPTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class EventSource(StrEnum):
    RUNTIME = "runtime"
    AGENT_SDK = "agent_sdk"
    CODEX = "codex"
    VALIDATOR = "validator"
    OPERATOR = "operator"
    REFERENCE = "reference"
    MCP = "mcp"


TERMINAL_TASK_STATUSES = frozenset(
    {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}
)
TERMINAL_RUN_STATUSES = frozenset(
    {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}
)


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    task_type: str
    status: TaskStatus
    input_sha256: str
    protected_payload_ref: str | None
    agent_definition_id: str
    agent_definition_version: str
    created_at: str
    updated_at: str
    completed_at: str | None


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    task_id: str
    attempt: int
    status: RunStatus
    agent_definition_id: str
    agent_definition_version: str
    session_ref: str | None
    run_state_artifact_id: str | None
    trace_id: str | None
    codex_thread_id: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    created_at: str
    started_at: str | None
    completed_at: str | None


@dataclass(frozen=True)
class RunEventRecord:
    run_id: str
    sequence: int
    event_type: str
    source: EventSource
    occurred_at: str
    payload_schema_version: str
    payload_sha256: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    run_id: str
    artifact_type: str
    storage_path: str
    sha256: str
    byte_length: int
    media_type: str
    created_at: str
    verified_at: str | None
