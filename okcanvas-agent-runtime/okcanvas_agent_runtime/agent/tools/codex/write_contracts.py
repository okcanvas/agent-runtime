from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import Field

from okcanvas_agent_runtime.agent.tools.codex.readonly_contracts import CodexUsageSummary, TreeSnapshot
from okcanvas_agent_runtime.core.contracts import StrictModel, UsageSummary


CODEX_WRITE_SCHEMA_VERSION = "okcanvas-codex-write-run-v1"


class CodexWriteResult(StrictModel):
    summary: str = Field(min_length=1, max_length=4000)
    inspected_files: list[str] = Field(default_factory=list, max_length=100)
    modified_files: list[str] = Field(default_factory=list, max_length=20)
    commands_observed: list[str] = Field(default_factory=list, max_length=100)
    unverified: list[str] = Field(default_factory=list, max_length=100)


class GitChange(StrictModel):
    status: str = Field(min_length=1, max_length=2)
    path: str = Field(min_length=1, max_length=500)
    additions: int | None = Field(default=None, ge=0)
    deletions: int | None = Field(default=None, ge=0)
    binary: bool = False


class GitDiffSummary(StrictModel):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: int = Field(ge=0)
    files: list[str] = Field(default_factory=list)
    changes: list[GitChange] = Field(default_factory=list)
    untracked_files: list[str] = Field(default_factory=list)
    staged_files: list[str] = Field(default_factory=list)


class CodexWriteErrorCode(str, Enum):
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
    SDK_NOT_INSTALLED = "SDK_NOT_INSTALLED"
    SDK_VERSION_MISMATCH = "SDK_VERSION_MISMATCH"
    CODEX_CLI_NOT_INSTALLED = "CODEX_CLI_NOT_INSTALLED"
    CODEX_CLI_VERSION_UNREADABLE = "CODEX_CLI_VERSION_UNREADABLE"
    API_KEY_MISSING = "API_KEY_MISSING"
    AGENT_MODEL_NOT_CONFIGURED = "AGENT_MODEL_NOT_CONFIGURED"
    CODEX_MODEL_NOT_CONFIGURED = "CODEX_MODEL_NOT_CONFIGURED"
    CODEX_RUN_FAILED = "CODEX_RUN_FAILED"
    OUTPUT_CONTRACT_INVALID = "OUTPUT_CONTRACT_INVALID"
    WORKSPACE_NOT_MUTATED = "WORKSPACE_NOT_MUTATED"
    CODEX_EVENT_EVIDENCE_MISSING = "CODEX_EVENT_EVIDENCE_MISSING"
    CODEX_THREAD_ID_MISSING = "CODEX_THREAD_ID_MISSING"
    CHANGE_EVIDENCE_MISSING = "CHANGE_EVIDENCE_MISSING"
    MODIFIED_FILE_OUTSIDE_ALLOWLIST = "MODIFIED_FILE_OUTSIDE_ALLOWLIST"
    EXPECTED_FILE_NOT_MODIFIED = "EXPECTED_FILE_NOT_MODIFIED"
    REPORTED_CHANGE_MISMATCH = "REPORTED_CHANGE_MISMATCH"
    FILE_DELETION_NOT_ALLOWED = "FILE_DELETION_NOT_ALLOWED"
    UNTRACKED_FILE_NOT_ALLOWED = "UNTRACKED_FILE_NOT_ALLOWED"
    STAGED_CHANGE_NOT_ALLOWED = "STAGED_CHANGE_NOT_ALLOWED"
    BINARY_CHANGE_NOT_ALLOWED = "BINARY_CHANGE_NOT_ALLOWED"
    COMMIT_CHANGED = "COMMIT_CHANGED"
    WEB_SEARCH_EVENT_OBSERVED = "WEB_SEARCH_EVENT_OBSERVED"
    MCP_EVENT_OBSERVED = "MCP_EVENT_OBSERVED"
    AGENT_TOKEN_BUDGET_EXCEEDED = "AGENT_TOKEN_BUDGET_EXCEEDED"
    CODEX_TOKEN_BUDGET_EXCEEDED = "CODEX_TOKEN_BUDGET_EXCEEDED"
    EVIDENCE_WRITE_FAILED = "EVIDENCE_WRITE_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class CodexWriteError(StrictModel):
    code: CodexWriteErrorCode
    message: str
    retryable: bool = False
    detail_type: str | None = None


class CodexWriteEnvelope(StrictModel):
    schema_version: Literal["okcanvas-codex-write-run-v1"] = CODEX_WRITE_SCHEMA_VERSION
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
    workspace: str
    input_sha256: str
    live_call: bool
    baseline_commit: str | None = None
    final_commit: str | None = None
    before: TreeSnapshot | None = None
    after: TreeSnapshot | None = None
    mutation_detected: bool = False
    event_file: str | None = None
    event_count: int = Field(default=0, ge=0)
    event_sha256: str | None = None
    event_types: list[str] = Field(default_factory=list)
    item_types: list[str] = Field(default_factory=list)
    allowed_files: list[str] = Field(default_factory=list)
    expected_files: list[str] = Field(default_factory=list)
    verified_modified_files: list[str] = Field(default_factory=list)
    diff: GitDiffSummary | None = None
    patch_file: str | None = None
    patch_sha256: str | None = None
    result: CodexWriteResult | None = None
    agent_usage: UsageSummary = Field(default_factory=UsageSummary)
    codex_usage: CodexUsageSummary = Field(default_factory=CodexUsageSummary)
    error: CodexWriteError | None = None
