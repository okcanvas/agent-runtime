from __future__ import annotations

import uuid
from typing import Protocol, cast

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.domain.attachments.errors import AttachmentError
from okcanvas_agent_runtime.application.ports import AttachmentStorePort, GovernedRunAdmissionPort, ProjectSnapshotStorePort, ProtectedPayloadStorePort, RunSubmissionStorePort
from okcanvas_agent_runtime.domain.project_snapshots.errors import ProjectSnapshotError
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.application.execution import GenericAgentExecutionService
from okcanvas_agent_runtime.agent.runtime import RuntimeBindingResolver
from okcanvas_agent_runtime.application.execution.contracts import GenericExecutionEnvelope
from okcanvas_agent_runtime.application.execution.service import PreparedGenericExecution

from okcanvas_agent_runtime.application.submissions.errors import RunSubmissionConfirmationError, RunSubmissionIntegrityError, RunSubmissionStateError
from okcanvas_agent_runtime.application.submissions.lifecycle import GovernedLifecyclePolicy
from okcanvas_agent_runtime.application.submissions.models import GovernedRunSubmissionResult, OrphanedRunReconciliationResult, RunExecutionOwnershipTransition, RecoveryResult, RunSubmissionDecision, RunSubmissionExecutionMode, RunSubmissionRecordState
from okcanvas_agent_runtime.application.submissions.policy import RunSubmissionPolicyCatalog
from okcanvas_agent_runtime.application.submissions.service import RunSubmissionBoundaryService


class PreparedExecutionScheduler(Protocol):
    async def schedule_prepared(self, *, prepared, settings: RuntimeSettings): ...


class GovernedReadOnlyRunSubmissionService:
    """Confirm, claim, recover, and schedule encrypted read-only submissions."""

    def __init__(
        self,
        *,
        project_root: str,
        store: RunSubmissionStorePort,
        protected_payload_store: ProtectedPayloadStorePort,
        admission_store: GovernedRunAdmissionPort | None = None,
        execution_service: GenericAgentExecutionService,
        runtime_bindings: RuntimeBindingResolver,
        scheduler: PreparedExecutionScheduler,
        owner_id: str | None = None,
        lifecycle_policy: GovernedLifecyclePolicy | None = None,
        attachment_store: AttachmentStorePort | None = None,
        project_snapshot_store: ProjectSnapshotStorePort | None = None,
    ) -> None:
        self._policy = RunSubmissionPolicyCatalog(project_root).resolve()
        self._store = store
        self._admission = admission_store or cast(GovernedRunAdmissionPort, store)
        self._payloads = protected_payload_store
        self._execution = execution_service
        self._definitions = AgentDefinitionCatalog(project_root)
        self._runtime_bindings = runtime_bindings
        self._scheduler = scheduler
        self._owner_id = owner_id or f"local-process-{uuid.uuid4().hex}"
        self._lifecycle = lifecycle_policy or GovernedLifecyclePolicy()
        self._attachments = attachment_store
        self._project_snapshots = project_snapshot_store

    @property
    def owner_id(self) -> str:
        return self._owner_id

    def reconcile_orphaned_running(
        self, *, limit: int = 100
    ) -> OrphanedRunReconciliationResult:
        candidates = self._store.list_orphaned_running(
            current_owner_id=self._owner_id, limit=limit
        )
        reconciled_submission_ids: list[str] = []
        reconciled_run_ids: list[str] = []
        skipped = 0
        failed = 0
        for decision in candidates:
            try:
                updated = self._store.reconcile_orphaned_running(
                    decision.submission_id,
                    current_owner_id=self._owner_id,
                    failed_payload_retention_days=self._lifecycle.failed_payload_retention_days,
                )
                if updated.state is RunSubmissionRecordState.EXECUTION_FAILED:
                    reconciled_submission_ids.append(updated.submission_id)
                    if updated.run_id:
                        reconciled_run_ids.append(updated.run_id)
                else:
                    skipped += 1
            except (RunSubmissionStateError, RunSubmissionIntegrityError):
                failed += 1
        return OrphanedRunReconciliationResult(
            scanned=len(candidates),
            reconciled=len(reconciled_submission_ids),
            skipped=skipped,
            failed=failed,
            submission_ids=tuple(reconciled_submission_ids),
            run_ids=tuple(reconciled_run_ids),
        )

    async def confirm_and_schedule(
        self,
        *,
        submission_id: str,
        confirmation: str,
        settings: RuntimeSettings,
        ownership_transition: RunExecutionOwnershipTransition | None = None,
    ) -> GovernedRunSubmissionResult | GenericExecutionEnvelope:
        decision = self._store.get(submission_id)
        if decision.execution_mode is not RunSubmissionExecutionMode.IMMEDIATE_AFTER_CONFIRMATION:
            raise RunSubmissionStateError(
                "Only read-only immediate submissions are executable in STEP019"
            )
        if not RunSubmissionBoundaryService.confirmation_matches(decision, confirmation):
            raise RunSubmissionConfirmationError(
                "Confirmation must exactly match the submission fingerprint challenge"
            )
        return await self._schedule(
            decision=decision,
            settings=settings,
            allow_recovery=False,
            ownership_transition=ownership_transition,
        )

    async def recover_stale(
        self,
        *,
        settings_factory,
        limit: int = 100,
    ) -> RecoveryResult:
        candidates = self._store.list_recoverable(limit=limit)
        recovered: list[str] = []
        skipped = 0
        failed = 0
        for decision in candidates:
            try:
                settings = settings_factory(decision)
                result = await self._schedule(
                    decision=decision,
                    settings=settings,
                    allow_recovery=True,
                    ownership_transition=None,
                )
                if isinstance(result, GovernedRunSubmissionResult) and result.scheduled:
                    recovered.append(decision.submission_id)
                else:
                    skipped += 1
            except Exception:
                failed += 1
        return RecoveryResult(
            scanned=len(candidates),
            recovered=len(recovered),
            skipped=skipped,
            failed=failed,
            submission_ids=tuple(recovered),
        )

    async def _schedule(
        self,
        *,
        decision: RunSubmissionDecision,
        settings: RuntimeSettings,
        allow_recovery: bool,
        ownership_transition: RunExecutionOwnershipTransition | None,
    ) -> GovernedRunSubmissionResult | GenericExecutionEnvelope:
        if decision.policy_sha256 != self._policy.policy_sha256:
            raise RunSubmissionIntegrityError(
                "Run submission policy changed after the request was fingerprinted"
            )
        if settings.model != decision.model:
            raise RunSubmissionIntegrityError(
                "Execution model does not match the fingerprinted submission model"
            )
        current_definition = self._definitions.resolve(decision.agent_definition_id)
        current_binding = self._runtime_bindings.resolve(current_definition)
        if (
            not decision.runtime_binding_sha256
            or current_binding.runtime_binding_sha256 != decision.runtime_binding_sha256
        ):
            raise RunSubmissionIntegrityError(
                "Executable Runtime binding changed after the request was fingerprinted"
            )
        if not allow_recovery and decision.state in {
            RunSubmissionRecordState.EXECUTION_CLAIMED,
            RunSubmissionRecordState.EXECUTION_SCHEDULED,
            RunSubmissionRecordState.EXECUTION_STARTED,
            RunSubmissionRecordState.EXECUTION_SUCCEEDED,
            RunSubmissionRecordState.EXECUTION_FAILED,
            RunSubmissionRecordState.EXECUTION_CANCELLED,
        }:
            if decision.task_id is None or decision.run_id is None:
                raise RunSubmissionIntegrityError(
                    "Executed submission has no Product Task/Run binding"
                )
            current = self._admission.create_governed_task_run(
                decision.submission_id,
                ownership_transition=ownership_transition,
            )
            return GovernedRunSubmissionResult(
                submission=current,
                task_id=current.task_id or "",
                run_id=current.run_id or "",
                scheduled=False,
                replayed=True,
            )
        payload = self._read_bound_payload(decision)
        prepared_attachment = None
        if payload.attachment is not None:
            if self._attachments is None:
                raise RunSubmissionIntegrityError(
                    "Submission attachment store is not configured"
                )
            try:
                prepared_attachment = self._attachments.read_bound(
                    payload.attachment, decision.submission_id
                )
            except AttachmentError as exc:
                raise RunSubmissionIntegrityError(str(exc)) from exc
        prepared_project_snapshot = None
        if payload.project_snapshot is not None:
            if self._project_snapshots is None:
                raise RunSubmissionIntegrityError(
                    "Submission project snapshot store is not configured"
                )
            try:
                prepared_project_snapshot = self._project_snapshots.read_bound(
                    payload.project_snapshot, decision.submission_id
                )
            except ProjectSnapshotError as exc:
                raise RunSubmissionIntegrityError(str(exc)) from exc
        if current_definition.workspace_access == "sandbox-readonly-v1":
            if prepared_project_snapshot is None:
                raise RunSubmissionIntegrityError(
                    "Sandbox read-only submission has no immutable project snapshot"
                )
        elif prepared_project_snapshot is not None:
            raise RunSubmissionIntegrityError(
                "Non-sandbox submission contains a project snapshot binding"
            )

        current = decision
        if allow_recovery:
            if current.task_id is None or current.run_id is None:
                raise RunSubmissionIntegrityError(
                    "Recovery candidate has no Product Task/Run binding"
                )
        else:
            current = self._admission.create_governed_task_run(
                decision.submission_id,
                ownership_transition=ownership_transition,
            )

        if current.state in {
            RunSubmissionRecordState.EXECUTION_STARTED,
            RunSubmissionRecordState.EXECUTION_SUCCEEDED,
            RunSubmissionRecordState.EXECUTION_FAILED,
            RunSubmissionRecordState.EXECUTION_CANCELLED,
        }:
            return GovernedRunSubmissionResult(
                submission=current,
                task_id=current.task_id or "",
                run_id=current.run_id or "",
                scheduled=False,
                replayed=True,
            )

        prepared = self._execution.prepare_existing(
            task_id=current.task_id or "",
            run_id=current.run_id or "",
            agent_definition_id=current.agent_definition_id,
            expected_definition_version=current.agent_definition_version,
            expected_definition_sha256=current.agent_definition_sha256,
            expected_runtime_binding_sha256=current.runtime_binding_sha256,
            expected_input_sha256=current.input_sha256,
            expected_payload_ref=current.protected_payload_ref or "",
            request=payload.request,
            settings=settings,
            session_id=current.session_id,
            attachment=prepared_attachment,
            project_snapshot=prepared_project_snapshot,
            delegated_mcp_identity=payload.delegated_mcp_identity,
        )
        if isinstance(prepared, GenericExecutionEnvelope):
            return prepared

        claim = self._store.claim_execution(
            current.submission_id,
            owner_id=self._owner_id,
            lease_seconds=self._lifecycle.claim_lease_seconds,
            max_attempts=self._lifecycle.max_claim_attempts,
            allow_recovery=allow_recovery,
        )
        if claim is None:
            latest = self._store.get(current.submission_id)
            return GovernedRunSubmissionResult(
                submission=latest,
                task_id=latest.task_id or "",
                run_id=latest.run_id or "",
                scheduled=False,
                replayed=True,
            )

        guarded = PreparedGenericExecution(
            task_id=prepared.task_id,
            run_id=prepared.run_id,
            definition=prepared.definition,
            request=prepared.request,
            runtime_binding_sha256=prepared.runtime_binding_sha256,
            session_id=prepared.session_id,
            attachment=prepared.attachment,
            project_snapshot=prepared.project_snapshot,
            delegated_mcp_identity=prepared.delegated_mcp_identity,
            start_execution=lambda: self._store.begin_execution(
                current.submission_id, claim_token=claim.token
            ),
            continue_execution=lambda: self._store.execution_fence_active(
                current.submission_id, claim_token=claim.token
            ),
        )
        await self._scheduler.schedule_prepared(prepared=guarded, settings=settings)
        latest = self._store.mark_scheduled(
            current.submission_id,
            claim_token=claim.token,
        )
        return GovernedRunSubmissionResult(
            submission=latest,
            task_id=claim.task_id,
            run_id=claim.run_id,
            scheduled=True,
            replayed=False,
        )

    def _read_bound_payload(self, decision: RunSubmissionDecision):
        if (
            not decision.protected_payload_persisted
            or not decision.protected_payload_ref
            or not decision.protected_payload_sha256
            or decision.protected_payload_byte_length is None
            or decision.protected_payload_key_id != self._payloads.key.key_id
        ):
            raise RunSubmissionIntegrityError(
                "Submission does not have a valid protected payload binding"
            )
        payload = self._payloads.read(
            decision.protected_payload_ref,
            expected_file_sha256=decision.protected_payload_sha256,
            expected_byte_length=decision.protected_payload_byte_length,
        )
        if (
            payload.submission_id != decision.submission_id
            or payload.agent_definition_id != decision.agent_definition_id
            or payload.agent_definition_version != decision.agent_definition_version
            or payload.agent_definition_sha256 != decision.agent_definition_sha256
            or payload.runtime_binding_sha256 != decision.runtime_binding_sha256
            or payload.session_id != decision.session_id
            or payload.model != decision.model
            or payload.input_sha256 != decision.input_sha256
            or payload.request_fingerprint_sha256 != decision.request_fingerprint_sha256
            or (
                payload.project_snapshot.snapshot_sha256
                if payload.project_snapshot is not None else None
            ) != decision.project_snapshot_sha256
            or (
                payload.project_snapshot.archive_sha256
                if payload.project_snapshot is not None else None
            ) != decision.project_snapshot_archive_sha256
            or (
                payload.project_snapshot.file_count
                if payload.project_snapshot is not None else None
            ) != decision.project_snapshot_file_count
            or (
                payload.project_snapshot.total_bytes
                if payload.project_snapshot is not None else None
            ) != decision.project_snapshot_total_bytes
        ):
            raise RunSubmissionIntegrityError(
                "Decrypted payload identity does not match the submission ledger"
            )
        return payload
