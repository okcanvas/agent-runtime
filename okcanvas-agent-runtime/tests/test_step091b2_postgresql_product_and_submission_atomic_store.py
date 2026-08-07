from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from okcanvas_agent_runtime.adapters.persistence.postgresql import (
    PostgreSQLConnectionSettings,
    PostgreSQLProductStore,
    PostgreSQLRunSubmissionStore,
    PostgreSQLServiceResourceOwnershipStore,
)
from okcanvas_agent_runtime.application.submissions.models import (
    ProtectedPayloadRetentionState,
    RunExecutionOwnershipTransition,
    RunSubmissionDecision,
    RunSubmissionExecutionMode,
    RunSubmissionRecordState,
)
from okcanvas_agent_runtime.bootstrap.application import create_app
from okcanvas_agent_runtime.bootstrap.storage_topology import StorageTopologyError

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 64


class _EmulatedCursor:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
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
        if normalized.startswith("ALTER TABLE run_submission_preflight ADD COLUMN IF NOT EXISTS"):
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
            uri,
            uri=True,
            isolation_level=None,
            check_same_thread=False,
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
            self.uri,
            uri=True,
            isolation_level=None,
            check_same_thread=False,
        )

    def connect(self, settings: PostgreSQLConnectionSettings) -> _EmulatedConnection:
        assert settings.dsn_sha256
        return _EmulatedConnection(self.uri)

    def close(self) -> None:
        self.anchor.close()


def _decision(submission_id: str = "submission_step091b2") -> RunSubmissionDecision:
    return RunSubmissionDecision(
        submission_id=submission_id,
        state=RunSubmissionRecordState.READY_FOR_CONFIRMATION,
        execution_mode=RunSubmissionExecutionMode.IMMEDIATE_AFTER_CONFIRMATION,
        policy_id="policy-step091b2",
        policy_version="1.0.0",
        policy_sha256=SHA,
        authority_scope="READ_ONLY",
        agent_definition_id="agent-step091b2",
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
        protected_payload_ref="payload_step091b2",
        protected_payload_sha256="d" * 64,
        protected_payload_key_id="key-step091b2",
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
        reasons=("step091b2",),
        created_at="2026-08-06T00:00:00Z",
    )


def _stores(emulator: _PostgreSQLEmulator):
    settings = PostgreSQLConnectionSettings(
        "postgresql://runtime:secret@db.example/okcanvas"
    )
    product = PostgreSQLProductStore(settings, connect_factory=emulator.connect)
    ownership = PostgreSQLServiceResourceOwnershipStore(
        settings, connect_factory=emulator.connect
    )
    submission = PostgreSQLRunSubmissionStore(settings, connect_factory=emulator.connect)
    product.initialize()
    ownership.initialize()
    submission.initialize()
    return settings, product, submission, ownership


def test_postgresql_settings_redact_dsn() -> None:
    settings = PostgreSQLConnectionSettings(
        "postgresql://runtime:top-secret@db.example/okcanvas"
    )
    assert "top-secret" not in repr(settings)
    assert "db.example" not in repr(settings)
    assert len(settings.dsn_sha256) == 64


def test_postgresql_atomic_admission_creates_product_and_ownership() -> None:
    emulator = _PostgreSQLEmulator("step091b2-admission")
    try:
        _, product, submission, ownership = _stores(emulator)
        decision = _decision()
        submission.register(decision)
        admitted = submission.create_governed_task_run(
            decision.submission_id,
            ownership_transition=RunExecutionOwnershipTransition(
                tenant_id="tenant-a", principal_id="user-001"
            ),
        )
        assert admitted.task_id and admitted.run_id
        assert product.get_task(admitted.task_id).status.value == "READY"
        assert product.get_run(admitted.run_id).status.value == "CREATED"
        events = product.list_events(admitted.run_id)
        assert [event.sequence for event in events] == [1]
        assert [event.event_type for event in events] == ["run.created"]
        assert ownership.get(resource_type="task", resource_id=admitted.task_id).tenant_id == "tenant-a"
        assert ownership.get(resource_type="run", resource_id=admitted.run_id).principal_id == "user-001"
        replay = submission.create_governed_task_run(decision.submission_id)
        assert replay.replayed is True
        assert replay.task_id == admitted.task_id
        assert replay.run_id == admitted.run_id
    finally:
        emulator.close()


def test_postgresql_admission_rolls_back_all_rows_on_ownership_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    emulator = _PostgreSQLEmulator("step091b2-rollback")
    try:
        _, product, submission, _ = _stores(emulator)
        decision = _decision("submission_step091b2_rollback")
        submission.register(replace(decision, idempotency_key_sha256="e" * 64))

        def fail(*args, **kwargs):
            raise RuntimeError("injected ownership failure")

        monkeypatch.setattr(submission, "_apply_execution_ownership_transition", fail)
        with pytest.raises(RuntimeError, match="injected ownership failure"):
            submission.create_governed_task_run(
                decision.submission_id,
                ownership_transition=RunExecutionOwnershipTransition(
                    tenant_id="tenant-a", principal_id="user-001"
                ),
            )
        current = submission.get(decision.submission_id)
        assert current.task_id is None
        assert current.run_id is None
        assert product.list_tasks()[1] == 0
        assert product.list_runs()[1] == 0
        assert product.artifact_count() == 0
    finally:
        emulator.close()


def test_postgresql_product_event_sequence_is_monotonic() -> None:
    emulator = _PostgreSQLEmulator("step091b2-events")
    try:
        _, product, _, _ = _stores(emulator)
        task = product.create_task(
            task_type="TEST",
            input_sha256=SHA,
            agent_definition_id="agent-step091b2",
            agent_definition_version="1.0.0",
        )
        run = product.create_run(task_id=task.task_id)
        product.append_event(
            run.run_id,
            event_type="custom.one",
            source=__import__(
                "okcanvas_agent_runtime.domain.runs.models", fromlist=["EventSource"]
            ).EventSource.RUNTIME,
        )
        product.append_event(
            run.run_id,
            event_type="custom.two",
            source=__import__(
                "okcanvas_agent_runtime.domain.runs.models", fromlist=["EventSource"]
            ).EventSource.RUNTIME,
        )
        assert [event.sequence for event in product.list_events(run.run_id)] == [1, 2, 3]
    finally:
        emulator.close()


def test_bootstrap_admits_explicit_postgresql_hybrid_topology(tmp_path: Path) -> None:
    emulator = _PostgreSQLEmulator("step091b2-bootstrap")
    try:
        app = create_app(
            project_root=ROOT,
            product_db=tmp_path / "local-control.sqlite3",
            artifact_root=tmp_path / "artifacts",
            evaluation_db=tmp_path / "evaluation.sqlite3",
            session_root=tmp_path / "sessions",
            admin_key="step091b2-admin-key-123456",
            gateway=object(),
            product_store_backend="postgresql-hybrid-v1",
            postgresql_dsn="postgresql://runtime:secret@db.example/okcanvas",
            postgresql_connect_factory=emulator.connect,
        )
        topology = app.state.storage_topology
        assert topology.backend_id == "postgresql-hybrid-v1"
        assert topology.transaction_owner_id == "postgresql-product-submission-governed-admission-v1"
        assert topology.submission_store is topology.governed_admission
        assert isinstance(topology.product_store, PostgreSQLProductStore)
        assert isinstance(topology.submission_store, PostgreSQLRunSubmissionStore)
        assert isinstance(topology.ownership_store, PostgreSQLServiceResourceOwnershipStore)
        with pytest.raises(StorageTopologyError):
            replace(
                topology,
                ownership_store=PostgreSQLServiceResourceOwnershipStore(
                    PostgreSQLConnectionSettings(
                        "postgresql://runtime:secret@other.example/okcanvas"
                    ),
                    connect_factory=emulator.connect,
                ),
            ).validate()
    finally:
        emulator.close()


def test_sqlite_topology_rejects_unused_postgresql_dsn(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must not be configured"):
        create_app(
            project_root=ROOT,
            product_db=tmp_path / "product.sqlite3",
            artifact_root=tmp_path / "artifacts",
            admin_key="step091b2-admin-key-123456",
            gateway=object(),
            postgresql_dsn="postgresql://runtime:secret@db.example/okcanvas",
        )
