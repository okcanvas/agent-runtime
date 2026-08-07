from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import re
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from okcanvas_agent_runtime.application.submissions.errors import RunSubmissionIdempotencyConflict, RunSubmissionIntegrityError, RunSubmissionNotFound, RunSubmissionStateError
from okcanvas_agent_runtime.application.submissions.models import ExecutionClaim, ProtectedPayloadRetentionState, RunSubmissionDecision, RunSubmissionExecutionMode, RunExecutionOwnershipTransition, RunSubmissionOwnershipTransition, RunSubmissionRecordState

_SCHEMA = """
CREATE TABLE IF NOT EXISTS run_submission_preflight (
    submission_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    execution_mode TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    policy_sha256 TEXT NOT NULL,
    authority_scope TEXT NOT NULL,
    agent_definition_id TEXT NOT NULL,
    agent_definition_version TEXT NOT NULL,
    agent_definition_sha256 TEXT NOT NULL,
    runtime_binding_sha256 TEXT,
    session_id TEXT,
    model TEXT,
    input_sha256 TEXT NOT NULL,
    request_fingerprint_sha256 TEXT NOT NULL,
    idempotency_key_sha256 TEXT NOT NULL UNIQUE,
    source_adapter_id TEXT,
    source_adapter_version TEXT,
    source_adapter_definition_sha256 TEXT,
    source_request_sha256 TEXT,
    source_snapshot_sha256 TEXT,
    source_acquired_at TEXT,
    project_snapshot_sha256 TEXT,
    project_snapshot_archive_sha256 TEXT,
    project_snapshot_file_count INTEGER,
    project_snapshot_total_bytes INTEGER,
    confirmation_challenge TEXT,
    approval_required INTEGER NOT NULL,
    executable_now INTEGER NOT NULL,
    protected_payload_persisted INTEGER NOT NULL,
    protected_payload_ref TEXT,
    protected_payload_sha256 TEXT,
    protected_payload_key_id TEXT,
    protected_payload_byte_length INTEGER,
    task_id TEXT,
    run_id TEXT,
    confirmed_at TEXT,
    payload_consumed_at TEXT,
    scheduled_at TEXT,
    claim_owner_id TEXT,
    claim_token_sha256 TEXT,
    claim_acquired_at TEXT,
    claim_expires_at TEXT,
    claim_attempts INTEGER NOT NULL DEFAULT 0,
    recovery_count INTEGER NOT NULL DEFAULT 0,
    last_recovered_at TEXT,
    execution_started_at TEXT,
    execution_completed_at TEXT,
    payload_retention_state TEXT NOT NULL DEFAULT 'ACTIVE',
    payload_delete_after TEXT,
    payload_deleted_at TEXT,
    payload_retention_reason TEXT,
    reasons_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_run_submission_created
ON run_submission_preflight(created_at DESC, submission_id DESC);
CREATE INDEX IF NOT EXISTS idx_run_submission_claim_expiry
ON run_submission_preflight(state, claim_expires_at);
CREATE INDEX IF NOT EXISTS idx_run_submission_payload_retention
ON run_submission_preflight(payload_retention_state, payload_delete_after);
CREATE UNIQUE INDEX IF NOT EXISTS idx_run_submission_task
ON run_submission_preflight(task_id) WHERE task_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_run_submission_run
ON run_submission_preflight(run_id) WHERE run_id IS NOT NULL;
"""

_MIGRATION_COLUMNS = {
    "runtime_binding_sha256": "TEXT",
    "session_id": "TEXT",
    "source_adapter_id": "TEXT",
    "source_adapter_version": "TEXT",
    "source_adapter_definition_sha256": "TEXT",
    "source_request_sha256": "TEXT",
    "source_snapshot_sha256": "TEXT",
    "source_acquired_at": "TEXT",
    "project_snapshot_sha256": "TEXT",
    "project_snapshot_archive_sha256": "TEXT",
    "project_snapshot_file_count": "INTEGER",
    "project_snapshot_total_bytes": "INTEGER",
    "protected_payload_ref": "TEXT",
    "protected_payload_sha256": "TEXT",
    "protected_payload_key_id": "TEXT",
    "protected_payload_byte_length": "INTEGER",
    "task_id": "TEXT",
    "run_id": "TEXT",
    "confirmed_at": "TEXT",
    "payload_consumed_at": "TEXT",
    "scheduled_at": "TEXT",
    "claim_owner_id": "TEXT",
    "claim_token_sha256": "TEXT",
    "claim_acquired_at": "TEXT",
    "claim_expires_at": "TEXT",
    "claim_attempts": "INTEGER NOT NULL DEFAULT 0",
    "recovery_count": "INTEGER NOT NULL DEFAULT 0",
    "last_recovered_at": "TEXT",
    "execution_started_at": "TEXT",
    "execution_completed_at": "TEXT",
    "payload_retention_state": "TEXT NOT NULL DEFAULT 'ACTIVE'",
    "payload_delete_after": "TEXT",
    "payload_deleted_at": "TEXT",
    "payload_retention_reason": "TEXT",
}


_SERVICE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")
_CONSUMABLE_SERVICE_RESOURCE_TYPES = frozenset({"attachment-slot", "project-snapshot-slot"})


def _utc_now_dt() -> datetime:
    return datetime.now(UTC)


def _format_time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _utc_now() -> str:
    return _format_time(_utc_now_dt())


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _identifier(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_payload(payload: dict[str, Any]) -> tuple[str, str]:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return encoded, hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class SQLiteRunSubmissionStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self.database_path,
            timeout=15.0,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 15000")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.executescript(_SCHEMA)
                columns = {
                    str(row["name"])
                    for row in connection.execute(
                        "PRAGMA table_info(run_submission_preflight)"
                    ).fetchall()
                }
                for name, declaration in _MIGRATION_COLUMNS.items():
                    if name not in columns:
                        connection.execute(
                            f"ALTER TABLE run_submission_preflight ADD COLUMN {name} {declaration}"
                        )
                connection.executescript(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_run_submission_task
                    ON run_submission_preflight(task_id) WHERE task_id IS NOT NULL;
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_run_submission_run
                    ON run_submission_preflight(run_id) WHERE run_id IS NOT NULL;
                    CREATE INDEX IF NOT EXISTS idx_run_submission_claim_expiry
                    ON run_submission_preflight(state, claim_expires_at);
                    CREATE INDEX IF NOT EXISTS idx_run_submission_payload_retention
                    ON run_submission_preflight(payload_retention_state, payload_delete_after);
                    """
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def register(
        self,
        decision: RunSubmissionDecision,
        *,
        ownership_transition: RunSubmissionOwnershipTransition | None = None,
    ) -> RunSubmissionDecision:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                existing = connection.execute(
                    "SELECT * FROM run_submission_preflight WHERE idempotency_key_sha256 = ?",
                    (decision.idempotency_key_sha256,),
                ).fetchone()
                if existing is not None:
                    if existing["request_fingerprint_sha256"] != decision.request_fingerprint_sha256:
                        raise RunSubmissionIdempotencyConflict(
                            "Idempotency key was already used for a different submission fingerprint"
                        )
                    if ownership_transition is not None:
                        self._apply_ownership_transition(
                            connection,
                            submission_id=str(existing["submission_id"]),
                            transition=ownership_transition,
                        )
                    connection.commit()
                    return self._from_row(existing, replayed=True)
                connection.execute(
                    """
                    INSERT INTO run_submission_preflight(
                        submission_id, state, execution_mode,
                        policy_id, policy_version, policy_sha256, authority_scope,
                        agent_definition_id, agent_definition_version, agent_definition_sha256,
                        runtime_binding_sha256, session_id, model, input_sha256, request_fingerprint_sha256,
                        idempotency_key_sha256, source_adapter_id, source_adapter_version,
                        source_adapter_definition_sha256, source_request_sha256,
                        source_snapshot_sha256, source_acquired_at,
                        project_snapshot_sha256, project_snapshot_archive_sha256,
                        project_snapshot_file_count, project_snapshot_total_bytes,
                        confirmation_challenge, approval_required, executable_now,
                        protected_payload_persisted,
                        protected_payload_ref, protected_payload_sha256,
                        protected_payload_key_id, protected_payload_byte_length,
                        task_id, run_id, confirmed_at, payload_consumed_at, scheduled_at,
                        claim_owner_id, claim_token_sha256, claim_acquired_at, claim_expires_at,
                        claim_attempts, recovery_count, last_recovered_at,
                        execution_started_at, execution_completed_at,
                        payload_retention_state, payload_delete_after, payload_deleted_at,
                        payload_retention_reason, reasons_json, created_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._decision_values(decision),
                )
                if ownership_transition is not None:
                    self._apply_ownership_transition(
                        connection,
                        submission_id=decision.submission_id,
                        transition=ownership_transition,
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return decision

    def find_by_idempotency_hash(self, digest: str) -> RunSubmissionDecision | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM run_submission_preflight WHERE idempotency_key_sha256 = ?",
                (digest,),
            ).fetchone()
        return self._from_row(row, replayed=True) if row is not None else None

    def find_by_run_id(self, run_id: str) -> RunSubmissionDecision | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM run_submission_preflight WHERE run_id = ?", (run_id,)
            ).fetchone()
        return self._from_row(row, replayed=False) if row is not None else None

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
    ) -> RunSubmissionDecision:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._require_submission(connection, submission_id)
                if bool(row["protected_payload_persisted"]):
                    if ownership_transition is not None:
                        self._apply_ownership_transition(
                            connection,
                            submission_id=submission_id,
                            transition=ownership_transition,
                        )
                    connection.commit()
                    return self._from_row(row, replayed=True)
                connection.execute(
                    """
                    UPDATE run_submission_preflight
                    SET protected_payload_persisted = 1,
                        protected_payload_ref = ?, protected_payload_sha256 = ?,
                        protected_payload_key_id = ?, protected_payload_byte_length = ?,
                        payload_retention_state = ?, payload_delete_after = ?
                    WHERE submission_id = ? AND protected_payload_persisted = 0
                    """,
                    (
                        payload_ref,
                        file_sha256,
                        key_id,
                        byte_length,
                        ProtectedPayloadRetentionState.ACTIVE.value,
                        delete_after,
                        submission_id,
                    ),
                )
                if ownership_transition is not None:
                    self._apply_ownership_transition(
                        connection,
                        submission_id=submission_id,
                        transition=ownership_transition,
                    )
                updated = self._require_submission(connection, submission_id)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._from_row(updated, replayed=True)

    def apply_ownership_transition(
        self,
        submission_id: str,
        transition: RunSubmissionOwnershipTransition,
    ) -> RunSubmissionDecision:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._require_submission(connection, submission_id)
                self._apply_ownership_transition(
                    connection,
                    submission_id=submission_id,
                    transition=transition,
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._from_row(row, replayed=True)

    def _apply_ownership_transition(
        self,
        connection: sqlite3.Connection,
        *,
        submission_id: str,
        transition: RunSubmissionOwnershipTransition,
    ) -> None:
        if (
            _SERVICE_ID_RE.fullmatch(transition.tenant_id) is None
            or _SERVICE_ID_RE.fullmatch(transition.principal_id) is None
            or _SERVICE_ID_RE.fullmatch(submission_id) is None
        ):
            raise RunSubmissionIntegrityError("Service ownership transition identity is invalid")
        normalized: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for resource_type, resource_id in transition.consumed_resources:
            key = (resource_type, resource_id)
            if (
                resource_type not in _CONSUMABLE_SERVICE_RESOURCE_TYPES
                or _SERVICE_ID_RE.fullmatch(resource_id) is None
                or key in seen
            ):
                raise RunSubmissionIntegrityError("Consumed service resource identity is invalid")
            seen.add(key)
            normalized.append(key)

        owner = connection.execute(
            "SELECT tenant_id,principal_id FROM service_resource_owner "
            "WHERE resource_type='submission' AND resource_id=?",
            (submission_id,),
        ).fetchone()
        if owner is None:
            connection.execute(
                "INSERT INTO service_resource_owner("
                "resource_type,resource_id,tenant_id,principal_id,created_at"
                ") VALUES('submission',?,?,?,?)",
                (submission_id, transition.tenant_id, transition.principal_id, _utc_now()),
            )
        elif (
            str(owner["tenant_id"]) != transition.tenant_id
            or str(owner["principal_id"]) != transition.principal_id
        ):
            raise RunSubmissionIntegrityError(
                "Submission ownership belongs to another service principal"
            )

        for resource_type, resource_id in normalized:
            consumed_owner = connection.execute(
                "SELECT tenant_id,principal_id FROM service_resource_owner "
                "WHERE resource_type=? AND resource_id=?",
                (resource_type, resource_id),
            ).fetchone()
            if consumed_owner is not None and (
                str(consumed_owner["tenant_id"]) != transition.tenant_id
                or str(consumed_owner["principal_id"]) != transition.principal_id
            ):
                raise RunSubmissionIntegrityError(
                    "Consumed binary ingress ownership belongs to another service principal"
                )
            connection.execute(
                "DELETE FROM service_resource_owner "
                "WHERE resource_type=? AND resource_id=? AND tenant_id=? AND principal_id=?",
                (
                    resource_type,
                    resource_id,
                    transition.tenant_id,
                    transition.principal_id,
                ),
            )

    def get(self, submission_id: str) -> RunSubmissionDecision:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM run_submission_preflight WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
        if row is None:
            raise RunSubmissionNotFound(f"Run submission preflight not found: {submission_id}")
        return self._from_row(row, replayed=False)

    def create_governed_task_run(
        self,
        submission_id: str,
        *,
        ownership_transition: RunExecutionOwnershipTransition | None = None,
    ) -> RunSubmissionDecision:
        """Create exactly one Product Task/Run and atomically bind service ownership."""
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._require_submission(connection, submission_id)
                if row["task_id"] is not None or row["run_id"] is not None:
                    if row["task_id"] is None or row["run_id"] is None:
                        raise RunSubmissionIntegrityError(
                            "Submission has a partial Product Task/Run binding"
                        )
                    if ownership_transition is not None:
                        self._apply_execution_ownership_transition(
                            connection,
                            task_id=str(row["task_id"]),
                            run_id=str(row["run_id"]),
                            transition=ownership_transition,
                        )
                    connection.commit()
                    return self._from_row(row, replayed=True)
                current_state = RunSubmissionRecordState(str(row["state"]))
                if current_state not in {
                    RunSubmissionRecordState.READY_FOR_CONFIRMATION,
                    RunSubmissionRecordState.APPROVAL_PATH_REQUIRED,
                }:
                    raise RunSubmissionStateError(
                        "Only a confirmed read-only or approval-interrupted submission can create a Run"
                    )
                if not bool(row["protected_payload_persisted"]) or not row["protected_payload_ref"]:
                    raise RunSubmissionIntegrityError(
                        "Confirmed submission has no protected payload reference"
                    )
                task_id = _identifier("task")
                run_id = _identifier("run")
                now = _utc_now()
                connection.execute(
                    """
                    INSERT INTO task(
                        task_id, task_type, status, input_sha256, protected_payload_ref,
                        agent_definition_id, agent_definition_version,
                        created_at, updated_at, completed_at
                    ) VALUES(?, ?, 'READY', ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        task_id,
                        ("GOVERNED_LOCAL_TOOL_APPROVAL" if current_state is RunSubmissionRecordState.APPROVAL_PATH_REQUIRED else "GOVERNED_GENERIC_AGENT_EXECUTION"),
                        row["input_sha256"],
                        row["protected_payload_ref"],
                        row["agent_definition_id"],
                        row["agent_definition_version"],
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO run(
                        run_id, task_id, attempt, status,
                        agent_definition_id, agent_definition_version,
                        created_at
                    ) VALUES(?, ?, 1, 'CREATED', ?, ?, ?)
                    """,
                    (
                        run_id,
                        task_id,
                        row["agent_definition_id"],
                        row["agent_definition_version"],
                        now,
                    ),
                )
                self._insert_event(
                    connection,
                    run_id=run_id,
                    event_type="run.created",
                    payload={
                        "attempt": 1,
                        "task_id": task_id,
                        "submission_id": submission_id,
                        "governed": True,
                    },
                    payload_schema_version="okcanvas-governed-run-created-v1",
                    occurred_at=now,
                )
                connection.execute(
                    """
                    UPDATE run_submission_preflight
                    SET state = ?, task_id = ?, run_id = ?,
                        confirmed_at = ?, payload_consumed_at = ?,
                        payload_delete_after = NULL
                    WHERE submission_id = ?
                    """,
                    (
                        RunSubmissionRecordState.RUN_CREATED.value,
                        task_id,
                        run_id,
                        now,
                        now,
                        submission_id,
                    ),
                )
                if ownership_transition is not None:
                    self._apply_execution_ownership_transition(
                        connection,
                        task_id=task_id,
                        run_id=run_id,
                        transition=ownership_transition,
                    )
                updated = self._require_submission(connection, submission_id)
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise RunSubmissionIntegrityError(
                    "Governed submission could not create an atomic Product Task/Run binding"
                ) from exc
            except Exception:
                connection.rollback()
                raise
        return self._from_row(updated, replayed=False)

    def _apply_execution_ownership_transition(
        self,
        connection: sqlite3.Connection,
        *,
        task_id: str,
        run_id: str,
        transition: RunExecutionOwnershipTransition,
    ) -> None:
        if (
            _SERVICE_ID_RE.fullmatch(transition.tenant_id) is None
            or _SERVICE_ID_RE.fullmatch(transition.principal_id) is None
            or _SERVICE_ID_RE.fullmatch(task_id) is None
            or _SERVICE_ID_RE.fullmatch(run_id) is None
        ):
            raise RunSubmissionIntegrityError(
                "Service Task/Run ownership transition identity is invalid"
            )
        created_at = _utc_now()
        for resource_type, resource_id in (("task", task_id), ("run", run_id)):
            owner = connection.execute(
                "SELECT tenant_id,principal_id FROM service_resource_owner "
                "WHERE resource_type=? AND resource_id=?",
                (resource_type, resource_id),
            ).fetchone()
            if owner is None:
                connection.execute(
                    "INSERT INTO service_resource_owner("
                    "resource_type,resource_id,tenant_id,principal_id,created_at"
                    ") VALUES(?,?,?,?,?)",
                    (
                        resource_type,
                        resource_id,
                        transition.tenant_id,
                        transition.principal_id,
                        created_at,
                    ),
                )
            elif (
                str(owner["tenant_id"]) != transition.tenant_id
                or str(owner["principal_id"]) != transition.principal_id
            ):
                raise RunSubmissionIntegrityError(
                    "Product Task/Run ownership belongs to another service principal"
                )

    def claim_execution(
        self,
        submission_id: str,
        *,
        owner_id: str,
        lease_seconds: int,
        max_attempts: int,
        allow_recovery: bool = False,
        now: datetime | None = None,
    ) -> ExecutionClaim | None:
        if not owner_id or len(owner_id) > 128:
            raise ValueError("owner_id must contain 1..128 characters")
        if not 5 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be 5..3600")
        if not 1 <= max_attempts <= 10:
            raise ValueError("max_attempts must be 1..10")
        now_dt = (now or _utc_now_dt()).astimezone(UTC)
        acquired_at = _format_time(now_dt)
        expires_at = _format_time(now_dt + timedelta(seconds=lease_seconds))
        token = secrets.token_urlsafe(32)
        token_sha = _sha256_text(token)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._require_submission(connection, submission_id)
                if row["task_id"] is None or row["run_id"] is None:
                    raise RunSubmissionIntegrityError(
                        "Execution claim requires a Product Task/Run binding"
                    )
                state = RunSubmissionRecordState(str(row["state"]))
                attempts = int(row["claim_attempts"] or 0)
                recovered = False
                claimable = state is RunSubmissionRecordState.RUN_CREATED
                if not claimable and allow_recovery and state in {
                    RunSubmissionRecordState.EXECUTION_CLAIMED,
                    RunSubmissionRecordState.EXECUTION_SCHEDULED,
                }:
                    expiry = _parse_time(row["claim_expires_at"])
                    if expiry is not None and expiry <= now_dt:
                        product = connection.execute(
                            """
                            SELECT t.status AS task_status, r.status AS run_status
                            FROM task t JOIN run r ON r.task_id = t.task_id
                            WHERE t.task_id = ? AND r.run_id = ?
                            """,
                            (row["task_id"], row["run_id"]),
                        ).fetchone()
                        if product is None:
                            raise RunSubmissionIntegrityError(
                                "Submission Product Task/Run binding disappeared"
                            )
                        if product["task_status"] == "READY" and product["run_status"] == "CREATED":
                            claimable = True
                            recovered = True
                if not claimable:
                    connection.commit()
                    return None
                if attempts >= max_attempts:
                    raise RunSubmissionStateError(
                        "Execution claim reached the configured recovery-attempt limit"
                    )
                new_attempts = attempts + 1
                recovery_count = int(row["recovery_count"] or 0) + (1 if recovered else 0)
                connection.execute(
                    """
                    UPDATE run_submission_preflight
                    SET state = ?, claim_owner_id = ?, claim_token_sha256 = ?,
                        claim_acquired_at = ?, claim_expires_at = ?, claim_attempts = ?,
                        recovery_count = ?, last_recovered_at = ?
                    WHERE submission_id = ?
                    """,
                    (
                        RunSubmissionRecordState.EXECUTION_CLAIMED.value,
                        owner_id,
                        token_sha,
                        acquired_at,
                        expires_at,
                        new_attempts,
                        recovery_count,
                        acquired_at if recovered else row["last_recovered_at"],
                        submission_id,
                    ),
                )
                if recovered:
                    self._insert_event(
                        connection,
                        run_id=str(row["run_id"]),
                        event_type="run.execution.recovered",
                        payload={
                            "submission_id": submission_id,
                            "claim_attempt": new_attempts,
                            "recovery_count": recovery_count,
                        },
                        payload_schema_version="okcanvas-governed-run-recovered-v1",
                        occurred_at=acquired_at,
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return ExecutionClaim(
            submission_id=submission_id,
            task_id=str(row["task_id"]),
            run_id=str(row["run_id"]),
            owner_id=owner_id,
            token=token,
            acquired_at=acquired_at,
            expires_at=expires_at,
            attempt=new_attempts,
            recovered=recovered,
        )

    def mark_scheduled(self, submission_id: str, *, claim_token: str) -> RunSubmissionDecision:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._require_submission(connection, submission_id)
                state = RunSubmissionRecordState(str(row["state"]))
                if state in {
                    RunSubmissionRecordState.EXECUTION_SCHEDULED,
                    RunSubmissionRecordState.EXECUTION_STARTED,
                    RunSubmissionRecordState.EXECUTION_SUCCEEDED,
                    RunSubmissionRecordState.EXECUTION_FAILED,
                    RunSubmissionRecordState.EXECUTION_CANCELLED,
                }:
                    connection.commit()
                    return self._from_row(row, replayed=True)
                if state is not RunSubmissionRecordState.EXECUTION_CLAIMED:
                    raise RunSubmissionStateError(
                        f"Submission cannot be marked scheduled from state {state.value}"
                    )
                self._require_claim_token(row, claim_token)
                connection.execute(
                    """
                    UPDATE run_submission_preflight
                    SET state = ?, scheduled_at = ?
                    WHERE submission_id = ?
                    """,
                    (
                        RunSubmissionRecordState.EXECUTION_SCHEDULED.value,
                        _utc_now(),
                        submission_id,
                    ),
                )
                updated = self._require_submission(connection, submission_id)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._from_row(updated, replayed=False)

    def begin_execution(self, submission_id: str, *, claim_token: str) -> bool:
        """Atomically validate the active generation and start Product Task/Run exactly once."""
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._require_submission(connection, submission_id)
                state = RunSubmissionRecordState(str(row["state"]))
                if state is RunSubmissionRecordState.EXECUTION_STARTED:
                    connection.commit()
                    return False
                if state not in {
                    RunSubmissionRecordState.EXECUTION_CLAIMED,
                    RunSubmissionRecordState.EXECUTION_SCHEDULED,
                }:
                    connection.commit()
                    return False
                expected_token = row["claim_token_sha256"]
                if not expected_token or not secrets.compare_digest(
                    str(expected_token), _sha256_text(claim_token)
                ):
                    connection.commit()
                    return False
                product = connection.execute(
                    """
                    SELECT t.status AS task_status, r.status AS run_status
                    FROM task t JOIN run r ON r.task_id = t.task_id
                    WHERE t.task_id = ? AND r.run_id = ?
                    """,
                    (row["task_id"], row["run_id"]),
                ).fetchone()
                if product is None:
                    raise RunSubmissionIntegrityError(
                        "Submission Product Task/Run binding disappeared"
                    )
                if product["task_status"] != "READY" or product["run_status"] != "CREATED":
                    connection.commit()
                    return False
                now = _utc_now()
                connection.execute(
                    "UPDATE task SET status = 'RUNNING', updated_at = ? WHERE task_id = ?",
                    (now, row["task_id"]),
                )
                connection.execute(
                    "UPDATE run SET status = 'RUNNING', started_at = ? WHERE run_id = ?",
                    (now, row["run_id"]),
                )
                self._insert_event(
                    connection,
                    run_id=str(row["run_id"]),
                    event_type="run.started",
                    payload={
                        "agent_definition_id": row["agent_definition_id"],
                        "agent_definition_version": row["agent_definition_version"],
                        "submission_id": submission_id,
                        "governed": True,
                        "claim_attempt": int(row["claim_attempts"] or 0),
                    },
                    payload_schema_version="okcanvas-governed-run-started-v1",
                    occurred_at=now,
                )
                connection.execute(
                    """
                    UPDATE run_submission_preflight
                    SET state = ?, execution_started_at = ?, claim_expires_at = NULL
                    WHERE submission_id = ?
                    """,
                    (RunSubmissionRecordState.EXECUTION_STARTED.value, now, submission_id),
                )
                connection.commit()
                return True
            except Exception:
                connection.rollback()
                raise

    def execution_fence_active(self, submission_id: str, *, claim_token: str) -> bool:
        """Return whether the exact governed execution generation may still persist work."""
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT s.state, s.claim_token_sha256, t.status AS task_status, r.status AS run_status
                FROM run_submission_preflight s
                JOIN task t ON t.task_id = s.task_id
                JOIN run r ON r.run_id = s.run_id
                WHERE s.submission_id = ?
                """,
                (submission_id,),
            ).fetchone()
        if row is None or row["state"] != RunSubmissionRecordState.EXECUTION_STARTED.value:
            return False
        expected = row["claim_token_sha256"]
        return bool(
            expected
            and secrets.compare_digest(str(expected), _sha256_text(claim_token))
            and row["task_status"] == "RUNNING"
            and row["run_status"] == "RUNNING"
        )

    def list_orphaned_running(
        self, *, current_owner_id: str, limit: int = 100
    ) -> list[RunSubmissionDecision]:
        if not current_owner_id or len(current_owner_id) > 128:
            raise ValueError("current_owner_id must contain 1..128 characters")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be 1..100")
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT s.*
                FROM run_submission_preflight s
                JOIN task t ON t.task_id = s.task_id
                JOIN run r ON r.run_id = s.run_id
                WHERE s.state = ?
                  AND s.claim_owner_id IS NOT NULL
                  AND s.claim_owner_id <> ?
                  AND t.status = 'RUNNING'
                  AND r.status = 'RUNNING'
                  AND NOT EXISTS (SELECT 1 FROM artifact a WHERE a.run_id = s.run_id)
                ORDER BY s.execution_started_at, s.submission_id
                LIMIT ?
                """,
                (RunSubmissionRecordState.EXECUTION_STARTED.value, current_owner_id, limit),
            ).fetchall()
        return [self._from_row(row, replayed=False) for row in rows]

    def list_terminal_outcome_reconciliation_candidates(
        self, *, current_owner_id: str, limit: int = 100
    ) -> list[RunSubmissionDecision]:
        """List terminal Product outcomes whose governed submission/retention is incomplete."""
        if not current_owner_id or len(current_owner_id) > 128:
            raise ValueError("current_owner_id must contain 1..128 characters")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be 1..100")
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT s.*
                FROM run_submission_preflight s
                JOIN task t ON t.task_id = s.task_id
                JOIN run r ON r.run_id = s.run_id
                WHERE r.status IN ('SUCCEEDED', 'FAILED', 'CANCELLED')
                  AND t.status = r.status
                  AND (
                        (s.state = ? AND s.claim_owner_id IS NOT NULL AND s.claim_owner_id <> ?)
                        OR s.state IN (?, ?, ?)
                      )
                  AND (
                        s.state <> CASE r.status
                            WHEN 'SUCCEEDED' THEN ?
                            WHEN 'FAILED' THEN ?
                            WHEN 'CANCELLED' THEN ?
                        END
                        OR s.claim_owner_id IS NOT NULL
                        OR s.claim_token_sha256 IS NOT NULL
                        OR (r.status = 'SUCCEEDED' AND (
                            s.payload_retention_state <> ?
                            OR s.protected_payload_persisted <> 0
                        ))
                        OR (r.status IN ('FAILED', 'CANCELLED') AND (
                            s.payload_retention_state <> ?
                            OR s.payload_delete_after IS NULL
                        ))
                        OR NOT EXISTS (
                            SELECT 1 FROM run_event e
                            WHERE e.run_id = s.run_id
                              AND e.event_type = 'payload.retention.applied'
                        )
                      )
                ORDER BY r.completed_at, s.submission_id
                LIMIT ?
                """,
                (
                    RunSubmissionRecordState.EXECUTION_STARTED.value,
                    current_owner_id,
                    RunSubmissionRecordState.EXECUTION_SUCCEEDED.value,
                    RunSubmissionRecordState.EXECUTION_FAILED.value,
                    RunSubmissionRecordState.EXECUTION_CANCELLED.value,
                    RunSubmissionRecordState.EXECUTION_SUCCEEDED.value,
                    RunSubmissionRecordState.EXECUTION_FAILED.value,
                    RunSubmissionRecordState.EXECUTION_CANCELLED.value,
                    ProtectedPayloadRetentionState.DELETED.value,
                    ProtectedPayloadRetentionState.RETAINED.value,
                    limit,
                ),
            ).fetchall()
        return [self._from_row(row, replayed=False) for row in rows]

    def reconcile_orphaned_running(
        self,
        submission_id: str,
        *,
        current_owner_id: str,
        failed_payload_retention_days: int,
        now: datetime | None = None,
    ) -> RunSubmissionDecision:
        """Fail one previous-process RUNNING execution without re-executing it."""
        if not current_owner_id or len(current_owner_id) > 128:
            raise ValueError("current_owner_id must contain 1..128 characters")
        if not 1 <= failed_payload_retention_days <= 90:
            raise ValueError("failed_payload_retention_days must be 1..90")
        now_dt = (now or _utc_now_dt()).astimezone(UTC)
        occurred_at = _format_time(now_dt)
        delete_after = _format_time(now_dt + timedelta(days=failed_payload_retention_days))
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._require_submission(connection, submission_id)
                state = RunSubmissionRecordState(str(row["state"]))
                if state is RunSubmissionRecordState.EXECUTION_FAILED:
                    connection.commit()
                    return self._from_row(row, replayed=True)
                if state is not RunSubmissionRecordState.EXECUTION_STARTED:
                    raise RunSubmissionStateError(
                        "Only a started governed execution can be reconciled after process loss"
                    )
                previous_owner = row["claim_owner_id"]
                if not previous_owner or secrets.compare_digest(
                    str(previous_owner), current_owner_id
                ):
                    raise RunSubmissionStateError(
                        "Current-process execution cannot be reconciled as orphaned"
                    )
                product = connection.execute(
                    """
                    SELECT t.status AS task_status, r.status AS run_status,
                           (SELECT COUNT(*) FROM artifact a WHERE a.run_id = r.run_id) AS artifact_count
                    FROM task t JOIN run r ON r.task_id = t.task_id
                    WHERE t.task_id = ? AND r.run_id = ?
                    """,
                    (row["task_id"], row["run_id"]),
                ).fetchone()
                if product is None:
                    raise RunSubmissionIntegrityError(
                        "Submission Product Task/Run binding disappeared"
                    )
                if product["task_status"] != "RUNNING" or product["run_status"] != "RUNNING":
                    raise RunSubmissionIntegrityError(
                        "Orphan reconciliation requires RUNNING Product Task and Run"
                    )
                if int(product["artifact_count"]) != 0:
                    raise RunSubmissionIntegrityError(
                        "A Run with a persisted Artifact cannot be reconciled as orphaned"
                    )
                connection.execute(
                    """
                    UPDATE task
                    SET status = 'FAILED', updated_at = ?, completed_at = ?
                    WHERE task_id = ? AND status = 'RUNNING'
                    """,
                    (occurred_at, occurred_at, row["task_id"]),
                )
                connection.execute(
                    """
                    UPDATE run
                    SET status = 'FAILED', completed_at = ?
                    WHERE run_id = ? AND status = 'RUNNING'
                    """,
                    (occurred_at, row["run_id"]),
                )
                self._insert_event(
                    connection,
                    run_id=str(row["run_id"]),
                    event_type="run.execution.orphaned",
                    payload={
                        "submission_id": submission_id,
                        "previous_process_owner_changed": True,
                        "reexecution_attempted": False,
                    },
                    payload_schema_version="okcanvas-orphaned-run-detected-v1",
                    occurred_at=occurred_at,
                )
                self._insert_event(
                    connection,
                    run_id=str(row["run_id"]),
                    event_type="run.failed",
                    payload={
                        "code": "PROCESS_LOSS_RECONCILED",
                        "retryable": False,
                        "from_status": "RUNNING",
                        "to_status": "FAILED",
                    },
                    payload_schema_version="okcanvas-orphaned-run-failed-v1",
                    occurred_at=occurred_at,
                )
                self._insert_event(
                    connection,
                    run_id=str(row["run_id"]),
                    event_type="payload.retention.applied",
                    payload={
                        "state": "RETAINED",
                        "reason": "process-loss-investigation-window",
                        "delete_after": delete_after,
                    },
                    payload_schema_version="okcanvas-payload-retention-v1",
                    occurred_at=occurred_at,
                )
                connection.execute(
                    """
                    UPDATE run_submission_preflight
                    SET state = ?, execution_completed_at = ?,
                        claim_owner_id = NULL, claim_token_sha256 = NULL,
                        claim_acquired_at = NULL, claim_expires_at = NULL,
                        payload_retention_state = ?, payload_delete_after = ?,
                        payload_retention_reason = ?
                    WHERE submission_id = ?
                    """,
                    (
                        RunSubmissionRecordState.EXECUTION_FAILED.value,
                        occurred_at,
                        ProtectedPayloadRetentionState.RETAINED.value,
                        delete_after,
                        "process-loss-investigation-window",
                        submission_id,
                    ),
                )
                updated = self._require_submission(connection, submission_id)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._from_row(updated, replayed=False)

    def reconcile_terminal_outcome_ledger(
        self,
        submission_id: str,
        *,
        current_owner_id: str,
        failed_payload_retention_days: int,
        now: datetime | None = None,
    ) -> RunSubmissionDecision:
        """Align a governed submission ledger with an already-terminal Product outcome."""
        if not current_owner_id or len(current_owner_id) > 128:
            raise ValueError("current_owner_id must contain 1..128 characters")
        if not 1 <= failed_payload_retention_days <= 90:
            raise ValueError("failed_payload_retention_days must be 1..90")
        now_dt = (now or _utc_now_dt()).astimezone(UTC)
        occurred_at = _format_time(now_dt)
        retained_until = _format_time(
            now_dt + timedelta(days=failed_payload_retention_days)
        )
        state_by_status = {
            "SUCCEEDED": RunSubmissionRecordState.EXECUTION_SUCCEEDED,
            "FAILED": RunSubmissionRecordState.EXECUTION_FAILED,
            "CANCELLED": RunSubmissionRecordState.EXECUTION_CANCELLED,
        }
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._require_submission(connection, submission_id)
                product = connection.execute(
                    """
                    SELECT t.status AS task_status, r.status AS run_status
                    FROM task t JOIN run r ON r.task_id = t.task_id
                    WHERE t.task_id = ? AND r.run_id = ?
                    """,
                    (row["task_id"], row["run_id"]),
                ).fetchone()
                if product is None:
                    raise RunSubmissionIntegrityError(
                        "Submission Product Task/Run binding disappeared"
                    )
                run_status = str(product["run_status"])
                if run_status not in state_by_status or product["task_status"] != run_status:
                    raise RunSubmissionIntegrityError(
                        "Terminal reconciliation requires matching terminal Product Task and Run"
                    )
                current_state = RunSubmissionRecordState(str(row["state"]))
                allowed_states = {
                    RunSubmissionRecordState.EXECUTION_STARTED,
                    RunSubmissionRecordState.EXECUTION_SUCCEEDED,
                    RunSubmissionRecordState.EXECUTION_FAILED,
                    RunSubmissionRecordState.EXECUTION_CANCELLED,
                }
                if current_state not in allowed_states:
                    raise RunSubmissionStateError(
                        "Only a started or terminal governed execution can reconcile a terminal outcome"
                    )
                previous_owner = row["claim_owner_id"]
                if current_state is RunSubmissionRecordState.EXECUTION_STARTED:
                    if not previous_owner or secrets.compare_digest(
                        str(previous_owner), current_owner_id
                    ):
                        raise RunSubmissionStateError(
                            "Current-process terminal outcome cannot be reconciled as process loss"
                        )
                target_state = state_by_status[run_status]
                if current_state is not RunSubmissionRecordState.EXECUTION_STARTED and current_state is not target_state:
                    raise RunSubmissionIntegrityError(
                        "Submission terminal state conflicts with Product Run outcome"
                    )
                if run_status == "SUCCEEDED":
                    retention_state = ProtectedPayloadRetentionState.ACTIVE
                    delete_after = occurred_at
                    retention_reason = "successful-run-immediate-cleanup"
                else:
                    retention_state = ProtectedPayloadRetentionState.RETAINED
                    delete_after = retained_until
                    retention_reason = "terminal-failure-investigation-window"
                connection.execute(
                    """
                    UPDATE run_submission_preflight
                    SET state = ?, execution_completed_at = COALESCE(execution_completed_at, ?),
                        claim_owner_id = NULL, claim_token_sha256 = NULL,
                        claim_acquired_at = NULL, claim_expires_at = NULL,
                        payload_retention_state = ?, payload_delete_after = ?,
                        payload_retention_reason = ?
                    WHERE submission_id = ?
                    """,
                    (
                        target_state.value,
                        occurred_at,
                        retention_state.value,
                        delete_after,
                        retention_reason,
                        submission_id,
                    ),
                )
                updated = self._require_submission(connection, submission_id)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._from_row(updated, replayed=False)

    def terminalize(
        self,
        submission_id: str,
        *,
        run_status: str,
        payload_delete_after: str | None,
        retention_reason: str,
    ) -> RunSubmissionDecision:
        state_by_run = {
            "SUCCEEDED": RunSubmissionRecordState.EXECUTION_SUCCEEDED,
            "FAILED": RunSubmissionRecordState.EXECUTION_FAILED,
            "CANCELLED": RunSubmissionRecordState.EXECUTION_CANCELLED,
        }
        target = state_by_run.get(run_status)
        if target is None:
            raise ValueError("run_status must be terminal")
        retention_state = (
            ProtectedPayloadRetentionState.ACTIVE
            if run_status == "SUCCEEDED"
            else ProtectedPayloadRetentionState.RETAINED
        )
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._require_submission(connection, submission_id)
                if row["run_id"] is None:
                    raise RunSubmissionIntegrityError("Submission has no Run binding")
                product = connection.execute(
                    "SELECT status FROM run WHERE run_id = ?", (row["run_id"],)
                ).fetchone()
                if product is None or product["status"] != run_status:
                    raise RunSubmissionIntegrityError(
                        "Submission terminal state does not match Product Run"
                    )
                now = _utc_now()
                connection.execute(
                    """
                    UPDATE run_submission_preflight
                    SET state = ?, execution_completed_at = ?,
                        claim_owner_id = NULL, claim_token_sha256 = NULL,
                        claim_acquired_at = NULL, claim_expires_at = NULL,
                        payload_retention_state = ?, payload_delete_after = ?,
                        payload_retention_reason = ?
                    WHERE submission_id = ?
                    """,
                    (
                        target.value,
                        now,
                        retention_state.value,
                        payload_delete_after,
                        retention_reason,
                        submission_id,
                    ),
                )
                updated = self._require_submission(connection, submission_id)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._from_row(updated, replayed=False)

    def list_recoverable(self, *, now: datetime | None = None, limit: int = 100) -> list[RunSubmissionDecision]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be 1..100")
        threshold = _format_time((now or _utc_now_dt()).astimezone(UTC))
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT s.* FROM run_submission_preflight s
                JOIN task t ON t.task_id = s.task_id
                JOIN run r ON r.run_id = s.run_id
                WHERE s.state IN (?, ?)
                  AND s.claim_expires_at IS NOT NULL
                  AND s.claim_expires_at <= ?
                  AND t.status = 'READY'
                  AND r.status = 'CREATED'
                ORDER BY s.claim_expires_at, s.submission_id
                LIMIT ?
                """,
                (
                    RunSubmissionRecordState.EXECUTION_CLAIMED.value,
                    RunSubmissionRecordState.EXECUTION_SCHEDULED.value,
                    threshold,
                    limit,
                ),
            ).fetchall()
        return [self._from_row(row, replayed=False) for row in rows]

    def list_payload_cleanup_candidates(
        self, *, now: datetime | None = None, limit: int = 100
    ) -> list[RunSubmissionDecision]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be 1..100")
        threshold = _format_time((now or _utc_now_dt()).astimezone(UTC))
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM run_submission_preflight
                WHERE protected_payload_persisted = 1
                  AND payload_retention_state IN (?, ?)
                  AND payload_delete_after IS NOT NULL
                  AND payload_delete_after <= ?
                ORDER BY payload_delete_after, submission_id
                LIMIT ?
                """,
                (
                    ProtectedPayloadRetentionState.ACTIVE.value,
                    ProtectedPayloadRetentionState.RETAINED.value,
                    threshold,
                    limit,
                ),
            ).fetchall()
        return [self._from_row(row, replayed=False) for row in rows]

    def mark_payload_deleted(self, submission_id: str, *, reason: str) -> RunSubmissionDecision:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._require_submission(connection, submission_id)
                connection.execute(
                    """
                    UPDATE run_submission_preflight
                    SET payload_retention_state = ?, payload_deleted_at = ?,
                        payload_retention_reason = ?, protected_payload_persisted = 0
                    WHERE submission_id = ?
                    """,
                    (
                        ProtectedPayloadRetentionState.DELETED.value,
                        _utc_now(),
                        reason,
                        submission_id,
                    ),
                )
                updated = self._require_submission(connection, submission_id)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._from_row(updated, replayed=False)

    def mark_payload_delete_failed(self, submission_id: str, *, reason: str) -> RunSubmissionDecision:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._require_submission(connection, submission_id)
                connection.execute(
                    """
                    UPDATE run_submission_preflight
                    SET payload_retention_state = ?, payload_retention_reason = ?
                    WHERE submission_id = ?
                    """,
                    (
                        ProtectedPayloadRetentionState.DELETE_FAILED.value,
                        reason,
                        submission_id,
                    ),
                )
                updated = self._require_submission(connection, submission_id)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._from_row(updated, replayed=False)

    @staticmethod
    def _decision_values(decision: RunSubmissionDecision) -> tuple[object, ...]:
        return (
            decision.submission_id,
            decision.state.value,
            decision.execution_mode.value,
            decision.policy_id,
            decision.policy_version,
            decision.policy_sha256,
            decision.authority_scope,
            decision.agent_definition_id,
            decision.agent_definition_version,
            decision.agent_definition_sha256,
            decision.runtime_binding_sha256,
            decision.session_id,
            decision.model,
            decision.input_sha256,
            decision.request_fingerprint_sha256,
            decision.idempotency_key_sha256,
            decision.source_adapter_id,
            decision.source_adapter_version,
            decision.source_adapter_definition_sha256,
            decision.source_request_sha256,
            decision.source_snapshot_sha256,
            decision.source_acquired_at,
            decision.project_snapshot_sha256,
            decision.project_snapshot_archive_sha256,
            decision.project_snapshot_file_count,
            decision.project_snapshot_total_bytes,
            decision.confirmation_challenge,
            int(decision.approval_required),
            int(decision.executable_now),
            int(decision.protected_payload_persisted),
            decision.protected_payload_ref,
            decision.protected_payload_sha256,
            decision.protected_payload_key_id,
            decision.protected_payload_byte_length,
            decision.task_id,
            decision.run_id,
            decision.confirmed_at,
            decision.payload_consumed_at,
            decision.scheduled_at,
            decision.claim_owner_id,
            None,
            decision.claim_acquired_at,
            decision.claim_expires_at,
            decision.claim_attempts,
            decision.recovery_count,
            decision.last_recovered_at,
            decision.execution_started_at,
            decision.execution_completed_at,
            decision.payload_retention_state.value,
            decision.payload_delete_after,
            decision.payload_deleted_at,
            decision.payload_retention_reason,
            json.dumps(list(decision.reasons), ensure_ascii=False, separators=(",", ":")),
            decision.created_at,
        )

    @staticmethod
    def _from_row(row: sqlite3.Row, *, replayed: bool) -> RunSubmissionDecision:
        keys = set(row.keys())
        value = lambda key, default=None: row[key] if key in keys else default
        return RunSubmissionDecision(
            submission_id=str(row["submission_id"]),
            state=RunSubmissionRecordState(str(row["state"])),
            execution_mode=RunSubmissionExecutionMode(str(row["execution_mode"])),
            policy_id=str(row["policy_id"]),
            policy_version=str(row["policy_version"]),
            policy_sha256=str(row["policy_sha256"]),
            authority_scope=str(row["authority_scope"]),
            agent_definition_id=str(row["agent_definition_id"]),
            agent_definition_version=str(row["agent_definition_version"]),
            agent_definition_sha256=str(row["agent_definition_sha256"]),
            runtime_binding_sha256=(
                str(value("runtime_binding_sha256")) if value("runtime_binding_sha256") else ""
            ),
            session_id=(str(value("session_id")) if value("session_id") else None),
            model=str(row["model"]) if row["model"] is not None else None,
            input_sha256=str(row["input_sha256"]),
            request_fingerprint_sha256=str(row["request_fingerprint_sha256"]),
            idempotency_key_sha256=str(row["idempotency_key_sha256"]),
            source_adapter_id=(
                str(value("source_adapter_id")) if value("source_adapter_id") else None
            ),
            source_adapter_version=(
                str(value("source_adapter_version"))
                if value("source_adapter_version")
                else None
            ),
            source_adapter_definition_sha256=(
                str(value("source_adapter_definition_sha256"))
                if value("source_adapter_definition_sha256")
                else None
            ),
            source_request_sha256=(
                str(value("source_request_sha256"))
                if value("source_request_sha256")
                else None
            ),
            source_snapshot_sha256=(
                str(value("source_snapshot_sha256"))
                if value("source_snapshot_sha256")
                else None
            ),
            source_acquired_at=(
                str(value("source_acquired_at")) if value("source_acquired_at") else None
            ),
            project_snapshot_sha256=(
                str(value("project_snapshot_sha256"))
                if value("project_snapshot_sha256") else None
            ),
            project_snapshot_archive_sha256=(
                str(value("project_snapshot_archive_sha256"))
                if value("project_snapshot_archive_sha256") else None
            ),
            project_snapshot_file_count=(
                int(value("project_snapshot_file_count"))
                if value("project_snapshot_file_count") is not None else None
            ),
            project_snapshot_total_bytes=(
                int(value("project_snapshot_total_bytes"))
                if value("project_snapshot_total_bytes") is not None else None
            ),
            confirmation_challenge=(
                str(row["confirmation_challenge"])
                if row["confirmation_challenge"] is not None
                else None
            ),
            approval_required=bool(row["approval_required"]),
            executable_now=bool(row["executable_now"]),
            protected_payload_persisted=bool(row["protected_payload_persisted"]),
            protected_payload_ref=(
                str(row["protected_payload_ref"])
                if row["protected_payload_ref"] is not None
                else None
            ),
            protected_payload_sha256=(
                str(row["protected_payload_sha256"])
                if row["protected_payload_sha256"] is not None
                else None
            ),
            protected_payload_key_id=(
                str(row["protected_payload_key_id"])
                if row["protected_payload_key_id"] is not None
                else None
            ),
            protected_payload_byte_length=(
                int(row["protected_payload_byte_length"])
                if row["protected_payload_byte_length"] is not None
                else None
            ),
            task_id=str(row["task_id"]) if row["task_id"] is not None else None,
            run_id=str(row["run_id"]) if row["run_id"] is not None else None,
            confirmed_at=str(row["confirmed_at"]) if row["confirmed_at"] is not None else None,
            payload_consumed_at=(
                str(row["payload_consumed_at"])
                if row["payload_consumed_at"] is not None
                else None
            ),
            scheduled_at=str(row["scheduled_at"]) if row["scheduled_at"] is not None else None,
            claim_owner_id=(str(value("claim_owner_id")) if value("claim_owner_id") else None),
            claim_acquired_at=(
                str(value("claim_acquired_at")) if value("claim_acquired_at") else None
            ),
            claim_expires_at=(
                str(value("claim_expires_at")) if value("claim_expires_at") else None
            ),
            claim_attempts=int(value("claim_attempts", 0) or 0),
            recovery_count=int(value("recovery_count", 0) or 0),
            last_recovered_at=(
                str(value("last_recovered_at")) if value("last_recovered_at") else None
            ),
            execution_started_at=(
                str(value("execution_started_at")) if value("execution_started_at") else None
            ),
            execution_completed_at=(
                str(value("execution_completed_at")) if value("execution_completed_at") else None
            ),
            payload_retention_state=ProtectedPayloadRetentionState(
                str(value("payload_retention_state", "ACTIVE") or "ACTIVE")
            ),
            payload_delete_after=(
                str(value("payload_delete_after")) if value("payload_delete_after") else None
            ),
            payload_deleted_at=(
                str(value("payload_deleted_at")) if value("payload_deleted_at") else None
            ),
            payload_retention_reason=(
                str(value("payload_retention_reason"))
                if value("payload_retention_reason")
                else None
            ),
            reasons=tuple(json.loads(str(row["reasons_json"]))),
            created_at=str(row["created_at"]),
            replayed=replayed,
        )

    @staticmethod
    def _require_submission(connection: sqlite3.Connection, submission_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM run_submission_preflight WHERE submission_id = ?",
            (submission_id,),
        ).fetchone()
        if row is None:
            raise RunSubmissionNotFound(f"Run submission preflight not found: {submission_id}")
        return row

    @staticmethod
    def _require_claim_token(row: sqlite3.Row, token: str) -> None:
        expected = row["claim_token_sha256"]
        if not expected or not secrets.compare_digest(str(expected), _sha256_text(token)):
            raise RunSubmissionIntegrityError("Execution claim token is no longer active")

    @staticmethod
    def _insert_event(
        connection: sqlite3.Connection,
        *,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
        payload_schema_version: str,
        occurred_at: str,
    ) -> None:
        sequence = int(
            connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM run_event WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
        )
        encoded, digest = _canonical_payload(payload)
        connection.execute(
            """
            INSERT INTO run_event(
                run_id, sequence, event_type, source, occurred_at,
                payload_schema_version, payload_sha256, payload_json
            ) VALUES(?, ?, ?, 'operator', ?, ?, ?, ?)
            """,
            (
                run_id,
                sequence,
                event_type,
                occurred_at,
                payload_schema_version,
                digest,
                encoded,
            ),
        )
