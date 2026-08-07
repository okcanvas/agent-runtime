from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import Field

from okcanvas_agent_runtime.core.contracts import StrictModel, UsageSummary


APPROVAL_RECORD_SCHEMA_VERSION = "okcanvas-codex-write-approval-v1"
APPROVAL_PREPARE_SCHEMA_VERSION = "okcanvas-approval-prepare-v1"
APPROVAL_RESUME_SCHEMA_VERSION = "okcanvas-approval-resume-v1"


class ApprovalDecision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class ApprovalRecordState(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ApprovalErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    LIVE_OPT_IN_REQUIRED = "LIVE_OPT_IN_REQUIRED"
    WORKSPACE_TRUST_OPT_IN_REQUIRED = "WORKSPACE_TRUST_OPT_IN_REQUIRED"
    DISPOSABLE_WORKSPACE_OPT_IN_REQUIRED = "DISPOSABLE_WORKSPACE_OPT_IN_REQUIRED"
    WORKSPACE_WRITE_OPT_IN_REQUIRED = "WORKSPACE_WRITE_OPT_IN_REQUIRED"
    WORKSPACE_NOT_FOUND = "WORKSPACE_NOT_FOUND"
    GIT_REPOSITORY_REQUIRED = "GIT_REPOSITORY_REQUIRED"
    WORKSPACE_NOT_CLEAN = "WORKSPACE_NOT_CLEAN"
    WORKSPACE_SYMLINK_NOT_ALLOWED = "WORKSPACE_SYMLINK_NOT_ALLOWED"
    ARTIFACT_PATH_INSIDE_WORKSPACE = "ARTIFACT_PATH_INSIDE_WORKSPACE"
    APPROVAL_ARTIFACT_EXISTS = "APPROVAL_ARTIFACT_EXISTS"
    APPROVAL_RECORD_NOT_FOUND = "APPROVAL_RECORD_NOT_FOUND"
    RUN_STATE_NOT_FOUND = "RUN_STATE_NOT_FOUND"
    RUN_STATE_HASH_MISMATCH = "RUN_STATE_HASH_MISMATCH"
    APPROVAL_ALREADY_DECIDED = "APPROVAL_ALREADY_DECIDED"
    APPROVAL_INTERRUPTION_INVALID = "APPROVAL_INTERRUPTION_INVALID"
    APPROVAL_STATE_INVALID = "APPROVAL_STATE_INVALID"
    EXECUTION_ALREADY_CLAIMED = "EXECUTION_ALREADY_CLAIMED"
    SDK_NOT_INSTALLED = "SDK_NOT_INSTALLED"
    SDK_VERSION_MISMATCH = "SDK_VERSION_MISMATCH"
    CODEX_CLI_NOT_INSTALLED = "CODEX_CLI_NOT_INSTALLED"
    CODEX_CLI_VERSION_UNREADABLE = "CODEX_CLI_VERSION_UNREADABLE"
    API_KEY_MISSING = "API_KEY_MISSING"
    AGENT_MODEL_NOT_CONFIGURED = "AGENT_MODEL_NOT_CONFIGURED"
    CODEX_MODEL_NOT_CONFIGURED = "CODEX_MODEL_NOT_CONFIGURED"
    AGENT_RUN_FAILED = "AGENT_RUN_FAILED"
    CODEX_WRITE_FAILED = "CODEX_WRITE_FAILED"
    EVIDENCE_WRITE_FAILED = "EVIDENCE_WRITE_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ApprovalError(StrictModel):
    code: ApprovalErrorCode
    message: str
    retryable: bool = False
    detail_type: str | None = None


class ApprovalInterruption(StrictModel):
    tool_name: str
    call_id: str
    arguments_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ApprovalRecord(StrictModel):
    schema_version: Literal["okcanvas-codex-write-approval-v1"] = APPROVAL_RECORD_SCHEMA_VERSION
    approval_id: str
    execution_id: str
    state: ApprovalRecordState
    created_at: datetime
    updated_at: datetime
    decided_at: datetime | None = None
    execution_started_at: datetime | None = None
    execution_completed_at: datetime | None = None
    decision: ApprovalDecision | None = None
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    workspace: str
    state_file: str
    state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_file: str
    patch_file: str
    write_evidence_file: str
    allowed_files: list[str]
    expected_files: list[str]
    interruption: ApprovalInterruption
    agent_model: str
    codex_model: str
    codex_path: str | None = None
    request_id: str
    execution_count: int = Field(default=0, ge=0)
    write_run_id: str | None = None
    write_run_state: str | None = None
    write_run_sha256: str | None = None
    error: ApprovalError | None = None


class ApprovalPrepareEnvelope(StrictModel):
    schema_version: Literal["okcanvas-approval-prepare-v1"] = APPROVAL_PREPARE_SCHEMA_VERSION
    approval_id: str
    execution_id: str
    state: Literal["AWAITING_APPROVAL", "FAILED"]
    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)
    workspace: str
    request_sha256: str
    state_file: str | None = None
    state_sha256: str | None = None
    approval_file: str | None = None
    interruption: ApprovalInterruption | None = None
    workspace_unchanged: bool
    codex_called: bool = False
    trace_id: str | None = None
    response_id: str | None = None
    agent_usage: UsageSummary = Field(default_factory=UsageSummary)
    error: ApprovalError | None = None


class ApprovalResumeEnvelope(StrictModel):
    schema_version: Literal["okcanvas-approval-resume-v1"] = APPROVAL_RESUME_SCHEMA_VERSION
    approval_id: str
    execution_id: str
    state: Literal["SUCCEEDED", "REJECTED", "FAILED"]
    decision: ApprovalDecision
    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)
    workspace: str
    execution_count: int = Field(ge=0)
    workspace_mutated: bool
    write_run_id: str | None = None
    write_run_state: str | None = None
    write_run_sha256: str | None = None
    trace_id: str | None = None
    response_id: str | None = None
    agent_usage: UsageSummary = Field(default_factory=UsageSummary)
    error: ApprovalError | None = None
