from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.domain.runs.models import EventSource, RunStatus
from okcanvas_agent_runtime.domain.runs.ports import ProductStore
from okcanvas_agent_runtime.application.ports import AttachmentStorePort, ProjectSnapshotStorePort, ProtectedPayloadStorePort, RunSubmissionStorePort

from okcanvas_agent_runtime.application.submissions.errors import RunSubmissionPolicyError
from okcanvas_agent_runtime.application.submissions.models import RetentionCleanupResult, RunSubmissionRecordState, TerminalOutcomeReconciliationResult

_POLICY_KEYS = {
    "schema_version",
    "policy_id",
    "version",
    "claim_lease_seconds",
    "max_claim_attempts",
    "unconfirmed_payload_ttl_hours",
    "failed_payload_retention_days",
    "cleanup_batch_limit",
    "recovery_mode",
    "active_running_run_recovery_enabled",
    "distributed_worker_lease_enabled",
}


def _format(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _canonical_sha(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GovernedLifecyclePolicy:
    schema_version: str = "okcanvas-governed-execution-lifecycle-policy-v1"
    policy_id: str = "governed-execution-lifecycle"
    version: str = "1.0.0"
    claim_lease_seconds: int = 30
    max_claim_attempts: int = 3
    unconfirmed_payload_ttl_hours: int = 24
    failed_payload_retention_days: int = 7
    cleanup_batch_limit: int = 100
    recovery_mode: str = "explicit-local-operator"
    active_running_run_recovery_enabled: bool = False
    distributed_worker_lease_enabled: bool = False
    policy_sha256: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != "okcanvas-governed-execution-lifecycle-policy-v1":
            raise ValueError("Unsupported governed lifecycle policy schema")
        if not 5 <= self.claim_lease_seconds <= 3600:
            raise ValueError("claim_lease_seconds must be 5..3600")
        if not 1 <= self.max_claim_attempts <= 10:
            raise ValueError("max_claim_attempts must be 1..10")
        if not 1 <= self.unconfirmed_payload_ttl_hours <= 168:
            raise ValueError("unconfirmed_payload_ttl_hours must be 1..168")
        if not 1 <= self.failed_payload_retention_days <= 90:
            raise ValueError("failed_payload_retention_days must be 1..90")
        if not 1 <= self.cleanup_batch_limit <= 100:
            raise ValueError("cleanup_batch_limit must be 1..100")
        if self.recovery_mode != "explicit-local-operator":
            raise ValueError("Only explicit-local-operator recovery is supported")
        if self.active_running_run_recovery_enabled:
            raise ValueError("Active RUNNING Run recovery is not supported")
        if self.distributed_worker_lease_enabled:
            raise ValueError("Distributed worker leasing is not supported")

    def to_public_dict(self) -> dict[str, Any]:
        return asdict(self)


class GovernedLifecyclePolicyCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()

    def resolve(self) -> GovernedLifecyclePolicy:
        path = (
            self.project_root
            / "specs"
            / "submissions"
            / "governed-execution-lifecycle-policy.json"
        ).resolve()
        expected_parent = (self.project_root / "specs" / "submissions").resolve()
        if path.parent != expected_parent or path.is_symlink() or not path.is_file():
            raise RunSubmissionPolicyError("Governed lifecycle policy is missing or unsafe")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RunSubmissionPolicyError("Governed lifecycle policy is invalid JSON") from exc
        if not isinstance(payload, dict) or set(payload) != _POLICY_KEYS:
            raise RunSubmissionPolicyError("Governed lifecycle policy keys are invalid")
        digest = _canonical_sha(payload)
        try:
            return GovernedLifecyclePolicy(**payload, policy_sha256=digest)
        except (TypeError, ValueError) as exc:
            raise RunSubmissionPolicyError("Governed lifecycle policy values are invalid") from exc


class GovernedExecutionLifecycleService:
    """Synchronize terminal Run state and apply protected-payload retention rules."""

    def __init__(
        self,
        *,
        submission_store: RunSubmissionStorePort,
        product_store: ProductStore,
        payload_store: ProtectedPayloadStorePort,
        policy: GovernedLifecyclePolicy,
        attachment_store: AttachmentStorePort | None = None,
        project_snapshot_store: ProjectSnapshotStorePort | None = None,
    ) -> None:
        self._submissions = submission_store
        self._products = product_store
        self._payloads = payload_store
        self._attachments = attachment_store
        self._project_snapshots = project_snapshot_store
        self.policy = policy

    async def observe_run_completion(self, run_id: str, _result: object | None = None) -> None:
        submission = self._submissions.find_by_run_id(run_id)
        if submission is None:
            return
        run = self._products.get_run(run_id)
        if run.status not in {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}:
            return
        self._submissions.terminalize(
            submission.submission_id,
            run_status=run.status.value,
            payload_delete_after=self._terminal_delete_after(run.status),
            retention_reason=self._terminal_retention_reason(run.status),
        )
        self._apply_terminal_payload_and_event(
            submission_id=submission.submission_id,
            run_id=run_id,
            run_status=run.status,
        )

    def reconcile_terminal_outcomes(
        self, *, current_owner_id: str, limit: int = 100
    ) -> TerminalOutcomeReconciliationResult:
        """Reconcile already-terminal Product outcomes after observer process loss."""
        candidates = self._submissions.list_terminal_outcome_reconciliation_candidates(
            current_owner_id=current_owner_id, limit=limit
        )
        reconciled_submission_ids: list[str] = []
        reconciled_run_ids: list[str] = []
        deleted = 0
        retained = 0
        skipped = 0
        failed = 0
        for candidate in candidates:
            try:
                updated = self._submissions.reconcile_terminal_outcome_ledger(
                    candidate.submission_id,
                    current_owner_id=current_owner_id,
                    failed_payload_retention_days=self.policy.failed_payload_retention_days,
                )
                if not updated.run_id:
                    skipped += 1
                    continue
                run = self._products.get_run(updated.run_id)
                self._apply_terminal_payload_and_event(
                    submission_id=updated.submission_id,
                    run_id=updated.run_id,
                    run_status=run.status,
                )
                final = self._submissions.get(updated.submission_id)
                if final.state not in {
                    RunSubmissionRecordState.EXECUTION_SUCCEEDED,
                    RunSubmissionRecordState.EXECUTION_FAILED,
                    RunSubmissionRecordState.EXECUTION_CANCELLED,
                }:
                    skipped += 1
                    continue
                reconciled_submission_ids.append(final.submission_id)
                reconciled_run_ids.append(updated.run_id)
                if final.payload_retention_state.value == "DELETED":
                    deleted += 1
                elif final.payload_retention_state.value == "RETAINED":
                    retained += 1
            except Exception:
                failed += 1
        return TerminalOutcomeReconciliationResult(
            scanned=len(candidates),
            reconciled=len(reconciled_submission_ids),
            deleted=deleted,
            retained=retained,
            skipped=skipped,
            failed=failed,
            submission_ids=tuple(reconciled_submission_ids),
            run_ids=tuple(reconciled_run_ids),
        )

    def _apply_terminal_payload_and_event(
        self, *, submission_id: str, run_id: str, run_status: RunStatus
    ) -> None:
        decision = self._submissions.get(submission_id)
        existing = [
            item
            for item in self._products.list_events(run_id)
            if item.event_type == "payload.retention.applied"
        ]
        if run_status is RunStatus.SUCCEEDED:
            if decision.payload_retention_state.value != "DELETED" or decision.protected_payload_persisted:
                self._delete_payload(
                    decision.submission_id, decision.protected_payload_ref, "successful-run"
                )
            if not existing:
                self._products.append_event(
                    run_id,
                    event_type="payload.retention.applied",
                    source=EventSource.OPERATOR,
                    payload={"state": "DELETED", "reason": "successful-run"},
                    payload_schema_version="okcanvas-payload-retention-v1",
                )
            return
        delete_after = decision.payload_delete_after or self._terminal_delete_after(run_status)
        if not existing:
            self._products.append_event(
                run_id,
                event_type="payload.retention.applied",
                source=EventSource.OPERATOR,
                payload={
                    "state": "RETAINED",
                    "reason": "terminal-failure-investigation-window",
                    "delete_after": delete_after,
                },
                payload_schema_version="okcanvas-payload-retention-v1",
            )

    def _terminal_delete_after(self, run_status: RunStatus) -> str:
        if run_status is RunStatus.SUCCEEDED:
            return _format(datetime.now(UTC))
        return _format(
            datetime.now(UTC) + timedelta(days=self.policy.failed_payload_retention_days)
        )

    @staticmethod
    def _terminal_retention_reason(run_status: RunStatus) -> str:
        return (
            "successful-run-immediate-cleanup"
            if run_status is RunStatus.SUCCEEDED
            else "terminal-failure-investigation-window"
        )

    def cleanup_expired(self, *, now: datetime | None = None, limit: int | None = None) -> RetentionCleanupResult:
        candidates = self._submissions.list_payload_cleanup_candidates(
            now=now,
            limit=limit or self.policy.cleanup_batch_limit,
        )
        deleted: list[str] = []
        failed = 0
        for item in candidates:
            try:
                self._delete_payload(
                    item.submission_id,
                    item.protected_payload_ref,
                    "retention-deadline-expired",
                )
                deleted.append(item.submission_id)
            except Exception as exc:
                failed += 1
                self._submissions.mark_payload_delete_failed(
                    item.submission_id,
                    reason=f"delete-failed:{type(exc).__name__}",
                )
        return RetentionCleanupResult(
            scanned=len(candidates),
            deleted=len(deleted),
            retained=0,
            failed=failed,
            submission_ids=tuple(deleted),
        )

    def _delete_payload(self, submission_id: str, payload_ref: str | None, reason: str) -> None:
        attachment_ref = None
        project_snapshot_ref = None
        if payload_ref:
            decision = self._submissions.get(submission_id)
            if (
                decision.protected_payload_sha256
                and decision.protected_payload_byte_length is not None
            ):
                payload = self._payloads.read(
                    payload_ref,
                    expected_file_sha256=decision.protected_payload_sha256,
                    expected_byte_length=decision.protected_payload_byte_length,
                )
                if payload.attachment is not None:
                    if self._attachments is None:
                        raise RuntimeError(
                            "Protected payload references an attachment but no attachment store is configured"
                        )
                    attachment_ref = payload.attachment.attachment_ref
                if payload.project_snapshot is not None:
                    if self._project_snapshots is None:
                        raise RuntimeError(
                            "Protected payload references a project snapshot but no snapshot store is configured"
                        )
                    project_snapshot_ref = payload.project_snapshot.project_snapshot_ref
            if attachment_ref is not None:
                self._attachments.delete(attachment_ref)
            if project_snapshot_ref is not None:
                self._project_snapshots.delete(project_snapshot_ref)
            self._payloads.delete(payload_ref)
        self._submissions.mark_payload_deleted(submission_id, reason=reason)
