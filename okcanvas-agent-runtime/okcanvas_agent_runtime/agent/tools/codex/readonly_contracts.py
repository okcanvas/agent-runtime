from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import Field

from okcanvas_agent_runtime.core.contracts import StrictModel, UsageSummary


CODEX_SCHEMA_VERSION = "okcanvas-codex-readonly-run-v1"


class CodexFindingSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class CodexFinding(StrictModel):
    severity: CodexFindingSeverity
    title: str = Field(min_length=1, max_length=200)
    detail: str = Field(min_length=1, max_length=4000)
    evidence: list[str] = Field(default_factory=list, max_length=20)


class CodexReadOnlyResult(StrictModel):
    summary: str = Field(min_length=1, max_length=4000)
    inspected_files: list[str] = Field(default_factory=list, max_length=100)
    commands_observed: list[str] = Field(default_factory=list, max_length=100)
    findings: list[CodexFinding] = Field(default_factory=list, max_length=100)
    unverified: list[str] = Field(default_factory=list, max_length=100)


class TreeSnapshot(StrictModel):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    file_count: int = Field(ge=0)
    total_bytes: int = Field(ge=0)
    symlink_count: int = Field(default=0, ge=0)
    ignored_names: list[str] = Field(default_factory=list)


class CodexUsageSummary(StrictModel):
    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class CodexReadOnlyErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    LIVE_OPT_IN_REQUIRED = "LIVE_OPT_IN_REQUIRED"
    WORKSPACE_TRUST_OPT_IN_REQUIRED = "WORKSPACE_TRUST_OPT_IN_REQUIRED"
    WORKSPACE_NOT_FOUND = "WORKSPACE_NOT_FOUND"
    GIT_REPOSITORY_REQUIRED = "GIT_REPOSITORY_REQUIRED"
    WORKSPACE_SYMLINK_NOT_ALLOWED = "WORKSPACE_SYMLINK_NOT_ALLOWED"
    SDK_NOT_INSTALLED = "SDK_NOT_INSTALLED"
    SDK_VERSION_MISMATCH = "SDK_VERSION_MISMATCH"
    CODEX_CLI_NOT_INSTALLED = "CODEX_CLI_NOT_INSTALLED"
    CODEX_CLI_VERSION_UNREADABLE = "CODEX_CLI_VERSION_UNREADABLE"
    API_KEY_MISSING = "API_KEY_MISSING"
    AGENT_MODEL_NOT_CONFIGURED = "AGENT_MODEL_NOT_CONFIGURED"
    CODEX_MODEL_NOT_CONFIGURED = "CODEX_MODEL_NOT_CONFIGURED"
    CODEX_RUN_FAILED = "CODEX_RUN_FAILED"
    OUTPUT_CONTRACT_INVALID = "OUTPUT_CONTRACT_INVALID"
    WORKSPACE_MUTATED = "WORKSPACE_MUTATED"
    REQUIRED_FILE_NOT_DISCOVERED = "REQUIRED_FILE_NOT_DISCOVERED"
    THREAD_STATE_INVALID = "THREAD_STATE_INVALID"
    ARTIFACT_PATH_INSIDE_WORKSPACE = "ARTIFACT_PATH_INSIDE_WORKSPACE"
    CODEX_EVENT_EVIDENCE_MISSING = "CODEX_EVENT_EVIDENCE_MISSING"
    CODEX_THREAD_ID_MISSING = "CODEX_THREAD_ID_MISSING"
    INSPECTION_EVIDENCE_MISSING = "INSPECTION_EVIDENCE_MISSING"
    FILE_CHANGE_EVENT_OBSERVED = "FILE_CHANGE_EVENT_OBSERVED"
    WEB_SEARCH_EVENT_OBSERVED = "WEB_SEARCH_EVENT_OBSERVED"
    MCP_EVENT_OBSERVED = "MCP_EVENT_OBSERVED"
    COMMAND_EVIDENCE_MISSING = "COMMAND_EVIDENCE_MISSING"
    EVIDENCE_WRITE_FAILED = "EVIDENCE_WRITE_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class CodexReadOnlyError(StrictModel):
    code: CodexReadOnlyErrorCode
    message: str
    retryable: bool = False
    detail_type: str | None = None


class CodexReadOnlyEnvelope(StrictModel):
    schema_version: Literal["okcanvas-codex-readonly-run-v1"] = CODEX_SCHEMA_VERSION
    run_id: str
    request_id: str
    state: Literal["SUCCEEDED", "FAILED"]
    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)
    agent_model: str | None
    codex_model: str | None
    sdk_version: str | None
    codex_cli_version: str | None
    trace_id: str | None
    response_id: str | None
    thread_id: str | None
    resumed_thread: bool
    workspace: str
    input_sha256: str
    live_call: bool
    before: TreeSnapshot | None = None
    after: TreeSnapshot | None = None
    mutation_detected: bool = False
    event_file: str | None = None
    event_count: int = Field(default=0, ge=0)
    event_sha256: str | None = None
    event_types: list[str] = Field(default_factory=list)
    item_types: list[str] = Field(default_factory=list)
    required_files: list[str] = Field(default_factory=list)
    verified_inspected_files: list[str] = Field(default_factory=list)
    result: CodexReadOnlyResult | None = None
    agent_usage: UsageSummary = Field(default_factory=UsageSummary)
    codex_usage: CodexUsageSummary = Field(default_factory=CodexUsageSummary)
    error: CodexReadOnlyError | None = None
