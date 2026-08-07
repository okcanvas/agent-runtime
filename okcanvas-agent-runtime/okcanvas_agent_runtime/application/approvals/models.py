from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class ToolApprovalState(StrEnum):
    PENDING = "PENDING"
    APPROVING = "APPROVING"
    REJECTING = "REJECTING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ToolApprovalDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


@dataclass(frozen=True)
class ToolApprovalRecord:
    approval_id: str
    submission_id: str
    task_id: str
    run_id: str
    session_id: str | None
    session_item_count_before: int | None
    state: ToolApprovalState
    decision: ToolApprovalDecision | None
    tool_name: str
    tool_call_id_sha256: str
    arguments_sha256: str
    run_state_ref: str
    run_state_sha256: str
    run_state_byte_length: int
    run_state_key_id: str
    trace_id: str | None
    response_id: str | None
    tool_execution_count: int
    created_at: str
    decided_at: str | None
    completed_at: str | None

    def to_public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["decision"] = self.decision.value if self.decision else None
        return payload

    def to_inbox_dict(self) -> dict[str, Any]:
        """Return bounded operator metadata without storage or Tool payload details."""

        return {
            "approval_id": self.approval_id,
            "submission_id": self.submission_id,
            "task_id": self.task_id,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "state": self.state.value,
            "decision": self.decision.value if self.decision else None,
            "tool_name": self.tool_name,
            "trace_id": self.trace_id,
            "tool_execution_count": self.tool_execution_count,
            "created_at": self.created_at,
            "decided_at": self.decided_at,
            "completed_at": self.completed_at,
        }


from okcanvas_agent_protocols.approval import decision_confirmation_challenge


@dataclass(frozen=True)
class PersistedRunStateRecord:
    run_state_ref: str
    file_sha256: str
    byte_length: int
    key_id: str


@dataclass(frozen=True)
class ToolApprovalPrepareResult:
    record: ToolApprovalRecord
    replayed: bool = False


@dataclass(frozen=True)
class ToolApprovalResumeResult:
    record: ToolApprovalRecord
    task_id: str
    run_id: str
    state: str
    artifact_id: str | None
    tool_executed: bool
    replayed: bool
