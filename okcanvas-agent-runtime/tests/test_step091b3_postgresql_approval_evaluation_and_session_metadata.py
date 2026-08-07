from __future__ import annotations

import base64
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from okcanvas_agent_runtime.adapters.persistence.postgresql import (
    PostgreSQLConnectionSettings,
    PostgreSQLEvaluationStore,
    PostgreSQLProductStore,
    PostgreSQLRunSubmissionStore,
    PostgreSQLServiceResourceOwnershipStore,
    PostgreSQLSessionMetadataRuntimeService,
    PostgreSQLToolApprovalStore,
)
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.approvals.models import (
    ToolApprovalDecision,
    ToolApprovalState,
)
from okcanvas_agent_runtime.application.evaluation.models import EvaluationCase, EvaluationResult
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.application.submissions.models import (
    ProtectedPayloadRetentionState,
    RunSubmissionDecision,
    RunSubmissionExecutionMode,
    RunSubmissionRecordState,
)
from okcanvas_agent_runtime.bootstrap.application import create_app
from okcanvas_agent_runtime.domain.sessions import (
    SessionBusyError,
    SessionHistoryKey,
    SQLiteSessionPolicyCatalog,
)

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 64
KEY_TEXT = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")


class _EmulatedCursor:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._cursor = connection.cursor()

    @property
    def description(self):
        return self._cursor.description

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> "_EmulatedCursor":
        normalized = " ".join(sql.strip().split())
        if normalized.startswith("SELECT pg_advisory_xact_lock"):
            self._cursor.execute("SELECT 1")
            return self
        if normalized.startswith("ALTER TABLE") and "ADD COLUMN IF NOT EXISTS" in normalized:
            self._cursor.execute("SELECT 1 WHERE 0")
            return self
        translated = sql.replace("%s", "?").replace(" FOR UPDATE", "")
        if translated.strip().upper() == "BEGIN":
            translated = "BEGIN IMMEDIATE"
        self._cursor.execute(translated, params)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()


class _EmulatedConnection:
    def __init__(self, uri: str) -> None:
        self._connection = sqlite3.connect(
            uri, uri=True, isolation_level=None, check_same_thread=False
        )
        self.autocommit = True

    def cursor(self) -> _EmulatedCursor:
        return _EmulatedCursor(self._connection)

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


class _PostgreSQLEmulator:
    def __init__(self, name: str) -> None:
        self.uri = f"file:{name}?mode=memory&cache=shared"
        self.anchor = sqlite3.connect(
            self.uri, uri=True, isolation_level=None, check_same_thread=False
        )

    def connect(self, settings: PostgreSQLConnectionSettings) -> _EmulatedConnection:
        assert settings.dsn_sha256
        return _EmulatedConnection(self.uri)

    def close(self) -> None:
        self.anchor.close()


def _settings() -> PostgreSQLConnectionSettings:
    return PostgreSQLConnectionSettings(
        "postgresql://runtime:secret@db.example/okcanvas"
    )


def _decision(submission_id: str) -> RunSubmissionDecision:
    return RunSubmissionDecision(
        submission_id=submission_id,
        state=RunSubmissionRecordState.READY_FOR_CONFIRMATION,
        execution_mode=RunSubmissionExecutionMode.IMMEDIATE_AFTER_CONFIRMATION,
        policy_id="policy-step091b3",
        policy_version="1.0.0",
        policy_sha256=SHA,
        authority_scope="READ_ONLY",
        agent_definition_id="agent-step091b3",
        agent_definition_version="1.0.0",
        agent_definition_sha256=SHA,
        runtime_binding_sha256=SHA,
        session_id=None,
        model="gpt-test",
        input_sha256=SHA,
        request_fingerprint_sha256="b" * 64,
        idempotency_key_sha256="c" * 64,
        source_adapter_id=None,
        source_adapter_version=None,
        source_adapter_definition_sha256=None,
        source_request_sha256=None,
        source_snapshot_sha256=None,
        source_acquired_at=None,
        project_snapshot_sha256=None,
        project_snapshot_archive_sha256=None,
        project_snapshot_file_count=None,
        project_snapshot_total_bytes=None,
        confirmation_challenge="confirmed",
        approval_required=False,
        executable_now=True,
        protected_payload_persisted=True,
        protected_payload_ref="payload-step091b3",
        protected_payload_sha256="d" * 64,
        protected_payload_key_id="key-step091b3",
        protected_payload_byte_length=10,
        task_id=None,
        run_id=None,
        confirmed_at=None,
        payload_consumed_at=None,
        scheduled_at=None,
        claim_owner_id=None,
        claim_acquired_at=None,
        claim_expires_at=None,
        claim_attempts=0,
        recovery_count=0,
        last_recovered_at=None,
        execution_started_at=None,
        execution_completed_at=None,
        payload_retention_state=ProtectedPayloadRetentionState.ACTIVE,
        payload_delete_after=None,
        payload_deleted_at=None,
        payload_retention_reason=None,
        reasons=("step091b3",),
        created_at="2026-08-07T00:00:00Z",
    )


def test_postgresql_tool_approval_shares_product_transaction_domain() -> None:
    emulator = _PostgreSQLEmulator("step091b3-approval")
    try:
        settings = _settings()
        product = PostgreSQLProductStore(settings, connect_factory=emulator.connect)
        submission = PostgreSQLRunSubmissionStore(settings, connect_factory=emulator.connect)
        approval = PostgreSQLToolApprovalStore(settings, connect_factory=emulator.connect)
        for store in (product, submission, approval):
            store.initialize()

        decision = _decision("submission-step091b3-approval")
        submission.register(decision)
        admitted = submission.create_governed_task_run(decision.submission_id)
        claim = submission.claim_execution(
            decision.submission_id,
            owner_id="worker-step091b3",
            lease_seconds=60,
            max_attempts=3,
        )
        assert claim is not None
        assert submission.begin_execution(
            decision.submission_id, claim_token=claim.token
        ) is True

        pending = approval.create_pending(
            approval_id="approval-step091b3",
            submission_id=decision.submission_id,
            task_id=str(admitted.task_id),
            run_id=str(admitted.run_id),
            tool_name="local_text_metrics",
            tool_call_id_sha256="e" * 64,
            arguments_sha256="f" * 64,
            run_state_ref="run-state-step091b3",
            run_state_sha256="1" * 64,
            run_state_byte_length=128,
            run_state_key_id="key-step091b3",
            trace_id=None,
            response_id=None,
        )
        assert pending.state is ToolApprovalState.PENDING
        assert product.get_task(str(admitted.task_id)).status.value == "WAITING_APPROVAL"
        assert product.get_run(str(admitted.run_id)).status.value == "INTERRUPTED"
        assert submission.get(decision.submission_id).state.value == "WAITING_APPROVAL"

        deciding, replayed, token = approval.claim_decision(
            pending.approval_id, ToolApprovalDecision.APPROVE
        )
        assert deciding.state is ToolApprovalState.APPROVING
        assert replayed is False and token
        assert approval.begin_tool_execution(pending.approval_id, resume_token=token) is True
        assert approval.begin_tool_execution(pending.approval_id, resume_token=token) is False
        completed = approval.finish(
            pending.approval_id,
            state=ToolApprovalState.SUCCEEDED,
            tool_execution_count=1,
        )
        assert completed.state is ToolApprovalState.SUCCEEDED
        event_types = [event.event_type for event in product.list_events(str(admitted.run_id))]
        assert event_types[-4:] == [
            "tool.approval.requested",
            "run.interrupted",
            "tool.approval.decided",
            "run.resumed",
        ]
    finally:
        emulator.close()


def test_postgresql_evaluation_store_round_trip() -> None:
    emulator = _PostgreSQLEmulator("step091b3-evaluation")
    try:
        store = PostgreSQLEvaluationStore(_settings(), connect_factory=emulator.connect)
        store.initialize()
        case = EvaluationCase(
            case_id="case-step091b3",
            version="1.0.0",
            agent_definition_id="agent-step091b3",
            required_result={},
            forbidden_result={},
            required_tools=(),
            forbidden_tools=(),
            max_total_tokens=None,
            max_duration_ms=None,
            manifest_sha256=SHA,
        )
        result = EvaluationResult(
            evaluation_id="evaluation-step091b3",
            case_id=case.case_id,
            case_version=case.version,
            subject_run_id="run-step091b3",
            state="PASSED",
            checks={"ok": True},
            metrics={"total_tokens": 12},
            failures=(),
            created_at="2026-08-07T00:00:00Z",
        )
        store.save(
            case=case,
            envelope={
                "agent_definition_id": case.agent_definition_id,
                "runtime_binding_sha256": "b" * 64,
                "model": "gpt-test",
            },
            result=result,
        )
        loaded = store.get(result.evaluation_id)
        assert loaded["subject_runtime_binding_sha256"] == "b" * 64
        assert loaded["checks"] == {"ok": True}
        assert store.statistics()["evaluation_total"] == 1
    finally:
        emulator.close()


def test_postgresql_session_metadata_keeps_history_local(tmp_path: Path) -> None:
    emulator = _PostgreSQLEmulator("step091b3-session")
    try:
        settings = _settings()
        policy = SQLiteSessionPolicyCatalog(ROOT).resolve()
        runtime_a = PostgreSQLSessionMetadataRuntimeService(
            settings,
            tmp_path / "sessions",
            policy,
            SessionHistoryKey.from_text(KEY_TEXT),
            connect_factory=emulator.connect,
        )
        runtime_b = PostgreSQLSessionMetadataRuntimeService(
            settings,
            tmp_path / "sessions",
            policy,
            SessionHistoryKey.from_text(KEY_TEXT),
            connect_factory=emulator.connect,
        )
        runtime_a.initialize()
        runtime_b.initialize()
        definition = AgentDefinitionCatalog(ROOT).resolve("session-continuity-agent")
        binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
        record = runtime_a.create(
            definition=definition,
            runtime_binding_sha256=binding.runtime_binding_sha256,
        )
        assert runtime_b.get(record.session_id) == record
        acquired = runtime_a.acquire_turn(
            session_id=record.session_id,
            run_id="run-step091b3-a",
            definition=definition,
            runtime_binding_sha256=binding.runtime_binding_sha256,
        )
        assert acquired.active_run_id == "run-step091b3-a"
        with pytest.raises(SessionBusyError):
            runtime_b.acquire_turn(
                session_id=record.session_id,
                run_id="run-step091b3-b",
                definition=definition,
                runtime_binding_sha256=binding.runtime_binding_sha256,
            )
        released = runtime_b.release_turn(
            session_id=record.session_id,
            run_id="run-step091b3-a",
            succeeded=True,
            item_count=2,
        )
        assert released.turn_count == 1
        assert released.item_count == 2
        assert not runtime_a.catalog_db.exists()
        assert runtime_a.history_db.parent == (tmp_path / "sessions").resolve()
        assert runtime_a.metadata_backend_id == "postgresql-session-metadata-v1"
    finally:
        emulator.close()


def test_postgresql_hybrid_topology_uses_one_dsn_for_all_metadata(tmp_path: Path) -> None:
    emulator = _PostgreSQLEmulator("step091b3-bootstrap")
    try:
        app = create_app(
            project_root=ROOT,
            product_db=tmp_path / "local-control.sqlite3",
            artifact_root=tmp_path / "artifacts",
            evaluation_db=tmp_path / "evaluation.sqlite3",
            session_root=tmp_path / "sessions",
            admin_key="step091b3-admin-key-123456",
            gateway=object(),
            product_store_backend="postgresql-hybrid-v1",
            postgresql_dsn="postgresql://runtime:secret@db.example/okcanvas",
            postgresql_connect_factory=emulator.connect,
        )
        topology = app.state.storage_topology
        assert isinstance(topology.product_store, PostgreSQLProductStore)
        assert isinstance(topology.submission_store, PostgreSQLRunSubmissionStore)
        assert isinstance(topology.ownership_store, PostgreSQLServiceResourceOwnershipStore)
        assert isinstance(topology.tool_approval_store, PostgreSQLToolApprovalStore)
        assert isinstance(topology.evaluation_store, PostgreSQLEvaluationStore)
        assert isinstance(
            topology.session_runtime, PostgreSQLSessionMetadataRuntimeService
        )
        digests = {
            store.settings.dsn_sha256
            for store in (
                topology.product_store,
                topology.submission_store,
                topology.ownership_store,
                topology.tool_approval_store,
                topology.evaluation_store,
                topology.session_runtime,
            )
        }
        assert len(digests) == 1
    finally:
        emulator.close()
