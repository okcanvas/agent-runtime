from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class RunSubmissionExecutionMode(StrEnum):
    IMMEDIATE_AFTER_CONFIRMATION = "IMMEDIATE_AFTER_CONFIRMATION"
    APPROVAL_INTERRUPTED = "APPROVAL_INTERRUPTED"
    PROPOSAL_ONLY = "PROPOSAL_ONLY"


class RunSubmissionRecordState(StrEnum):
    READY_FOR_CONFIRMATION = "READY_FOR_CONFIRMATION"
    APPROVAL_PATH_REQUIRED = "APPROVAL_PATH_REQUIRED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVAL_RESUMING = "APPROVAL_RESUMING"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    PROPOSAL_ONLY = "PROPOSAL_ONLY"
    RUN_CREATED = "RUN_CREATED"
    EXECUTION_CLAIMED = "EXECUTION_CLAIMED"
    EXECUTION_SCHEDULED = "EXECUTION_SCHEDULED"
    EXECUTION_STARTED = "EXECUTION_STARTED"
    EXECUTION_SUCCEEDED = "EXECUTION_SUCCEEDED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    EXECUTION_CANCELLED = "EXECUTION_CANCELLED"


class ProtectedPayloadRetentionState(StrEnum):
    ACTIVE = "ACTIVE"
    RETAINED = "RETAINED"
    DELETED = "DELETED"
    DELETE_FAILED = "DELETE_FAILED"


@dataclass(frozen=True)
class RunSubmissionSourceBinding:
    adapter_id: str
    adapter_version: str
    adapter_definition_sha256: str
    source_request_sha256: str
    source_snapshot_sha256: str
    acquired_at: str

    def to_fingerprint_dict(self) -> dict[str, str]:
        return {
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "adapter_definition_sha256": self.adapter_definition_sha256,
            "source_request_sha256": self.source_request_sha256,
            "source_snapshot_sha256": self.source_snapshot_sha256,
        }


@dataclass(frozen=True)
class RunSubmissionOwnershipTransition:
    tenant_id: str
    principal_id: str
    roles: tuple[str, ...] = ()
    consumed_resources: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class RunExecutionOwnershipTransition:
    tenant_id: str
    principal_id: str
    roles: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunSubmissionPolicy:
    schema_version: str
    policy_id: str
    version: str
    authority_scope: str
    idempotency_required: bool
    idempotency_key_min_length: int
    idempotency_key_max_length: int
    input_max_chars: int
    confirmation_mode: str
    read_only_execution_mode: RunSubmissionExecutionMode
    local_tool_execution_mode: RunSubmissionExecutionMode
    write_mcp_execution_mode: RunSubmissionExecutionMode
    handoff_or_session_execution_mode: RunSubmissionExecutionMode
    protected_payload_mode: str
    direct_run_api_default_enabled: bool
    console_mutation_enabled: bool
    policy_sha256: str

    def to_public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "read_only_execution_mode",
            "local_tool_execution_mode",
            "write_mcp_execution_mode",
            "handoff_or_session_execution_mode",
        ):
            payload[key] = str(payload[key])
        return payload


@dataclass(frozen=True)
class RunSubmissionDecision:
    submission_id: str
    state: RunSubmissionRecordState
    execution_mode: RunSubmissionExecutionMode
    policy_id: str
    policy_version: str
    policy_sha256: str
    authority_scope: str
    agent_definition_id: str
    agent_definition_version: str
    agent_definition_sha256: str
    runtime_binding_sha256: str
    session_id: str | None
    model: str | None
    input_sha256: str
    request_fingerprint_sha256: str
    idempotency_key_sha256: str
    source_adapter_id: str | None
    source_adapter_version: str | None
    source_adapter_definition_sha256: str | None
    source_request_sha256: str | None
    source_snapshot_sha256: str | None
    source_acquired_at: str | None
    project_snapshot_sha256: str | None
    project_snapshot_archive_sha256: str | None
    project_snapshot_file_count: int | None
    project_snapshot_total_bytes: int | None
    confirmation_challenge: str | None
    approval_required: bool
    executable_now: bool
    protected_payload_persisted: bool
    protected_payload_ref: str | None
    protected_payload_sha256: str | None
    protected_payload_key_id: str | None
    protected_payload_byte_length: int | None
    task_id: str | None
    run_id: str | None
    confirmed_at: str | None
    payload_consumed_at: str | None
    scheduled_at: str | None
    claim_owner_id: str | None
    claim_acquired_at: str | None
    claim_expires_at: str | None
    claim_attempts: int
    recovery_count: int
    last_recovered_at: str | None
    execution_started_at: str | None
    execution_completed_at: str | None
    payload_retention_state: ProtectedPayloadRetentionState
    payload_delete_after: str | None
    payload_deleted_at: str | None
    payload_retention_reason: str | None
    reasons: tuple[str, ...]
    created_at: str
    replayed: bool = False

    def to_public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["execution_mode"] = self.execution_mode.value
        payload["payload_retention_state"] = self.payload_retention_state.value
        payload["reasons"] = list(self.reasons)
        # Claim tokens are never persisted or exposed. Owner is an opaque local instance ID.
        return payload


@dataclass(frozen=True)
class ExecutionClaim:
    submission_id: str
    task_id: str
    run_id: str
    owner_id: str
    token: str
    acquired_at: str
    expires_at: str
    attempt: int
    recovered: bool


@dataclass(frozen=True)
class GovernedRunSubmissionResult:
    submission: RunSubmissionDecision
    task_id: str
    run_id: str
    scheduled: bool
    replayed: bool

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "okcanvas-governed-run-submission-v1",
            "submission": self.submission.to_public_dict(),
            "task_id": self.task_id,
            "run_id": self.run_id,
            "scheduled": self.scheduled,
            "replayed": self.replayed,
        }


@dataclass(frozen=True)
class RecoveryResult:
    scanned: int
    recovered: int
    skipped: int
    failed: int
    submission_ids: tuple[str, ...]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "okcanvas-governed-recovery-result-v1",
            "scanned": self.scanned,
            "recovered": self.recovered,
            "skipped": self.skipped,
            "failed": self.failed,
            "submission_ids": list(self.submission_ids),
        }


@dataclass(frozen=True)
class OrphanedRunReconciliationResult:
    scanned: int
    reconciled: int
    skipped: int
    failed: int
    submission_ids: tuple[str, ...]
    run_ids: tuple[str, ...]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "okcanvas-orphaned-running-reconciliation-v1",
            "scanned": self.scanned,
            "reconciled": self.reconciled,
            "skipped": self.skipped,
            "failed": self.failed,
            "submission_ids": list(self.submission_ids),
            "run_ids": list(self.run_ids),
        }


@dataclass(frozen=True)
class TerminalOutcomeReconciliationResult:
    scanned: int
    reconciled: int
    deleted: int
    retained: int
    skipped: int
    failed: int
    submission_ids: tuple[str, ...]
    run_ids: tuple[str, ...]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "okcanvas-terminal-outcome-reconciliation-v1",
            "scanned": self.scanned,
            "reconciled": self.reconciled,
            "deleted": self.deleted,
            "retained": self.retained,
            "skipped": self.skipped,
            "failed": self.failed,
            "submission_ids": list(self.submission_ids),
            "run_ids": list(self.run_ids),
        }


@dataclass(frozen=True)
class RetentionCleanupResult:
    scanned: int
    deleted: int
    retained: int
    failed: int
    submission_ids: tuple[str, ...]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "okcanvas-protected-payload-retention-result-v1",
            "scanned": self.scanned,
            "deleted": self.deleted,
            "retained": self.retained,
            "failed": self.failed,
            "submission_ids": list(self.submission_ids),
        }
