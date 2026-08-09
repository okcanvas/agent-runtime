from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from okcanvas_agent_runtime.agent.definitions import AgentDefinition
from okcanvas_agent_runtime.application.approvals.models import (
    PersistedRunStateRecord,
    ToolApprovalDecision,
    ToolApprovalRecord,
    ToolApprovalState,
)
from okcanvas_agent_runtime.application.submissions.models import (
    ExecutionClaim,
    RunExecutionOwnershipTransition,
    RunSubmissionDecision,
    RunSubmissionOwnershipTransition,
)
from okcanvas_agent_runtime.application.submissions.protected_payload import (
    ProtectedPayloadContent,
    ProtectedPayloadRecord,
)
from okcanvas_agent_runtime.core.service_identity import ServicePrincipal
from okcanvas_agent_runtime.domain.attachments.policy import LocalAttachmentPolicy
from okcanvas_agent_runtime.domain.attachments.models import (
    AttachmentRecord,
    PreparedLocalAttachment,
    ProtectedAttachmentBinding,
)
from okcanvas_agent_runtime.domain.project_snapshots.policy import ProjectSnapshotPolicy
from okcanvas_agent_runtime.domain.project_snapshots.models import (
    PreparedProjectSnapshot,
    ProjectSnapshotRecord,
    ProtectedProjectSnapshotBinding,
)
from okcanvas_agent_runtime.domain.sessions.compaction import CompactionEventSink
from okcanvas_agent_runtime.domain.sessions.models import ProductSessionRecord
from okcanvas_agent_runtime.domain.sessions.context_focus import (
    SessionContextFocusObservation, SessionContextFocusRecord,
)

if TYPE_CHECKING:
    from okcanvas_agent_runtime.application.evaluation.models import EvaluationCase, EvaluationResult



@runtime_checkable
class RunSubmissionStorePort(Protocol):
    """Backend-neutral governed Submission ledger excluding Product admission ownership."""

    def initialize(self) -> None: ...

    def register(
        self,
        decision: RunSubmissionDecision,
        *,
        ownership_transition: RunSubmissionOwnershipTransition | None = None,
    ) -> RunSubmissionDecision: ...

    def get(self, submission_id: str) -> RunSubmissionDecision: ...

    def find_by_idempotency_hash(self, digest: str) -> RunSubmissionDecision | None: ...

    def find_by_run_id(self, run_id: str) -> RunSubmissionDecision | None: ...

    def attach_payload(
        self,
        submission_id: str,
        *,
        payload_ref: str,
        file_sha256: str,
        key_id: str,
        byte_length: int,
        delete_after: str | None = None,
        ownership_transition: RunSubmissionOwnershipTransition | None = None,
    ) -> RunSubmissionDecision: ...

    def apply_ownership_transition(
        self,
        submission_id: str,
        transition: RunSubmissionOwnershipTransition,
    ) -> RunSubmissionDecision: ...

    def claim_execution(
        self,
        submission_id: str,
        *,
        owner_id: str,
        lease_seconds: int,
        max_attempts: int,
        allow_recovery: bool = False,
        now: datetime | None = None,
    ) -> ExecutionClaim | None: ...

    def begin_execution(self, submission_id: str, *, claim_token: str) -> RunSubmissionDecision: ...

    def execution_fence_active(self, submission_id: str, *, claim_token: str) -> bool: ...

    def mark_scheduled(self, submission_id: str, *, claim_token: str) -> bool: ...

    def list_recoverable(
        self, *, current_owner_id: str, limit: int = 100
    ) -> list[RunSubmissionDecision]: ...

    def list_orphaned_running(
        self, *, current_owner_id: str, limit: int = 100
    ) -> list[RunSubmissionDecision]: ...

    def reconcile_orphaned_running(
        self,
        submission_id: str,
        *,
        current_owner_id: str,
        failed_payload_retention_days: int,
        now: datetime | None = None,
    ) -> RunSubmissionDecision: ...

    def terminalize(
        self,
        submission_id: str,
        *,
        run_status: str,
        payload_delete_after: str | None,
        retention_reason: str,
    ) -> RunSubmissionDecision: ...

    def list_payload_cleanup_candidates(
        self, *, now: datetime | None = None, limit: int = 100
    ) -> list[RunSubmissionDecision]: ...

    def mark_payload_deleted(self, submission_id: str, *, reason: str) -> RunSubmissionDecision: ...

    def mark_payload_delete_failed(
        self, submission_id: str, *, reason: str
    ) -> RunSubmissionDecision: ...

    def list_terminal_outcome_reconciliation_candidates(
        self, *, current_owner_id: str, limit: int = 100
    ) -> list[RunSubmissionDecision]: ...

    def reconcile_terminal_outcome_ledger(
        self,
        submission_id: str,
        *,
        current_owner_id: str,
        failed_payload_retention_days: int,
        now: datetime | None = None,
    ) -> RunSubmissionDecision: ...


@runtime_checkable
class GovernedRunAdmissionPort(Protocol):
    """Single transaction owner for Product Task/Run/Event and Submission binding admission."""

    def create_governed_task_run(
        self,
        submission_id: str,
        *,
        ownership_transition: RunExecutionOwnershipTransition | None = None,
    ) -> RunSubmissionDecision: ...


@runtime_checkable
class ProtectedPayloadStorePort(Protocol):
    @property
    def key(self) -> object: ...

    def initialize(self) -> None: ...

    def write(
        self, content: ProtectedPayloadContent, *, payload_ref: str | None = None
    ) -> ProtectedPayloadRecord: ...

    def read(
        self,
        payload_ref: str,
        *,
        expected_file_sha256: str,
        expected_byte_length: int,
    ) -> ProtectedPayloadContent: ...

    def delete(self, payload_ref: str) -> None: ...


@runtime_checkable
class AttachmentStorePort(Protocol):
    policy: LocalAttachmentPolicy

    def initialize(self) -> None: ...
    def create_slot(self, data: bytes, filename: str) -> AttachmentRecord: ...
    def inspect_slot(self, slot_ref: str) -> AttachmentRecord: ...
    def bind_slot(
        self, slot_ref: str, submission_id: str
    ) -> tuple[AttachmentRecord, ProtectedAttachmentBinding]: ...
    def read_bound(
        self, binding: ProtectedAttachmentBinding, submission_id: str
    ) -> PreparedLocalAttachment: ...
    def delete(self, record_ref: str) -> bool: ...
    def slot_exists(self, slot_ref: str) -> bool: ...
    def cleanup_expired_slots(self) -> int: ...
    def cleanup_expired_slot_refs(self) -> tuple[str, ...]: ...


@runtime_checkable
class ProjectSnapshotStorePort(Protocol):
    policy: ProjectSnapshotPolicy

    def initialize(self) -> None: ...
    def create_slot(self, data: bytes, filename: str) -> ProjectSnapshotRecord: ...
    def inspect_slot(self, slot_ref: str) -> ProjectSnapshotRecord: ...
    def bind_slot(
        self, slot_ref: str, submission_id: str
    ) -> tuple[ProjectSnapshotRecord, ProtectedProjectSnapshotBinding]: ...
    def read_bound(
        self, binding: ProtectedProjectSnapshotBinding, submission_id: str
    ) -> PreparedProjectSnapshot: ...
    def delete(self, record_ref: str) -> bool: ...
    def slot_exists(self, slot_ref: str) -> bool: ...
    def cleanup_expired_slots(self) -> int: ...
    def cleanup_expired_slot_refs(self) -> tuple[str, ...]: ...


@runtime_checkable
class RunStateStorePort(Protocol):
    def initialize(self) -> None: ...
    def write(
        self, *, approval_id: str, run_id: str, state_json: dict[str, Any]
    ) -> PersistedRunStateRecord: ...
    def read(
        self,
        *,
        approval_id: str,
        run_id: str,
        ref: str,
        expected_sha256: str,
        expected_byte_length: int,
    ) -> dict[str, Any]: ...
    def delete(self, ref: str) -> None: ...


@runtime_checkable
class ToolApprovalStorePort(Protocol):
    def initialize(self) -> None: ...
    def find_by_submission(self, submission_id: str) -> ToolApprovalRecord | None: ...
    def create_pending(
        self,
        *,
        approval_id: str,
        submission_id: str,
        task_id: str,
        run_id: str,
        tool_name: str,
        tool_call_id_sha256: str,
        arguments_sha256: str,
        run_state_ref: str,
        run_state_sha256: str,
        run_state_byte_length: int,
        run_state_key_id: str,
        trace_id: str | None,
        response_id: str | None,
        session_id: str | None = None,
        session_item_count_before: int | None = None,
    ) -> ToolApprovalRecord: ...
    def get(self, approval_id: str) -> ToolApprovalRecord: ...
    def list(
        self,
        *,
        state: ToolApprovalState | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ToolApprovalRecord], int]: ...
    def state_counts(self) -> dict[str, int]: ...
    def claim_decision(
        self, approval_id: str, decision: ToolApprovalDecision
    ) -> tuple[ToolApprovalRecord, bool, str | None]: ...
    def begin_tool_execution(self, approval_id: str, *, resume_token: str) -> bool: ...
    def finish(
        self,
        approval_id: str,
        *,
        state: ToolApprovalState,
        tool_execution_count: int,
    ) -> ToolApprovalRecord: ...


class ServiceResourceOwnerRecord(Protocol):
    resource_type: str
    resource_id: str
    tenant_id: str
    principal_id: str
    created_at: str


@runtime_checkable
class ServiceResourceOwnershipStorePort(Protocol):
    def initialize(self) -> None: ...
    def register(
        self, *, principal: ServicePrincipal, resource_type: str, resource_id: str
    ) -> ServiceResourceOwnerRecord: ...
    def get(self, *, resource_type: str, resource_id: str) -> ServiceResourceOwnerRecord: ...
    def require_principal(
        self, *, principal: ServicePrincipal, resource_type: str, resource_id: str
    ) -> ServiceResourceOwnerRecord: ...
    def require_tenant(
        self, *, principal: ServicePrincipal, resource_type: str, resource_id: str
    ) -> ServiceResourceOwnerRecord: ...
    def list_ids(
        self,
        *,
        principal: ServicePrincipal,
        resource_type: str,
        tenant_wide: bool = False,
        limit: int = 200,
    ) -> tuple[str, ...]: ...
    def release(self, *, principal: ServicePrincipal, resource_type: str, resource_id: str) -> None: ...
    def release_if_owned(
        self, *, principal: ServicePrincipal, resource_type: str, resource_id: str
    ) -> bool: ...
    def release_if_exists(self, *, resource_type: str, resource_id: str) -> bool: ...


@runtime_checkable
class EvaluationStorePort(Protocol):
    def initialize(self) -> None: ...
    def save(
        self, *, case: EvaluationCase, envelope: dict[str, Any], result: EvaluationResult
    ) -> None: ...
    def save_suite_bundle(
        self,
        *,
        evaluations: list[tuple[EvaluationCase, dict[str, Any], EvaluationResult]],
        suite_run: dict[str, Any],
        members: list[dict[str, Any]],
    ) -> None: ...
    def statistics(self) -> dict[str, object]: ...
    def get_suite_run(self, suite_run_id: str) -> dict[str, Any]: ...
    def list_suite_runs(
        self, *, suite_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]: ...
    def create_baseline(self, baseline: dict[str, Any]) -> None: ...
    def get_baseline(self, baseline_id: str) -> dict[str, Any]: ...
    def list_baselines(
        self, *, suite_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]: ...
    def get(self, evaluation_id: str) -> dict[str, Any]: ...
    def list_results(
        self,
        *,
        case_id: str | None = None,
        subject_run_id: str | None = None,
        state: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]: ...
    def list_case(self, case_id: str) -> list[dict[str, Any]]: ...


@runtime_checkable
class SessionKeyRotationRecord(Protocol):
    session_id: str
    operation_id: str | None
    source_key_id: str
    target_key_id: str
    item_count: int
    resumed: bool
    already_current: bool
    state: str


@runtime_checkable
class SessionRuntimePort(Protocol):
    def initialize(self) -> None: ...
    def create(
        self, *, definition: AgentDefinition, runtime_binding_sha256: str
    ) -> ProductSessionRecord: ...
    def get(self, session_id: str) -> ProductSessionRecord: ...
    def list(self, *, limit: int = 100) -> tuple[ProductSessionRecord, ...]: ...
    def get_context_focus(self, session_id: str) -> SessionContextFocusRecord | None: ...
    def validate_binding(
        self,
        *,
        session_id: str,
        definition: AgentDefinition,
        runtime_binding_sha256: str,
    ) -> ProductSessionRecord: ...
    def acquire_turn(
        self,
        *,
        session_id: str,
        run_id: str,
        definition: AgentDefinition,
        runtime_binding_sha256: str,
    ) -> ProductSessionRecord: ...
    def assert_active_turn(self, *, session_id: str, run_id: str) -> ProductSessionRecord: ...
    def release_turn(
        self,
        *,
        session_id: str,
        run_id: str,
        succeeded: bool | None = None,
        committed: bool | None = None,
        item_count: int,
        context_focus: SessionContextFocusObservation | None = None,
    ) -> ProductSessionRecord: ...
    def count_items(self, session_id: str) -> int: ...
    def sdk_session(self, session_id: str) -> object: ...
    def update_active_item_count(
        self, *, session_id: str, run_id: str, item_count: int
    ) -> ProductSessionRecord: ...
    async def compact_after_committed_turn(
        self,
        *,
        session_id: str,
        run_id: str,
        compaction_api_key: str | None,
        compaction_event_sink: CompactionEventSink | None = None,
    ) -> bool: ...
    def rollback_to_item_count(self, *, session_id: str, expected_item_count: int) -> int: ...
    def rotate_history_key(self, session_id: str) -> SessionKeyRotationRecord: ...
    def clear(self, session_id: str) -> ProductSessionRecord: ...
