from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from okcanvas_agent_runtime.domain.runs.errors import ArtifactIntegrityError, DuplicateRecordError, IntegrityContractError, RecordNotFoundError
from okcanvas_agent_runtime.domain.runs.models import TERMINAL_RUN_STATUSES, TERMINAL_TASK_STATUSES, AgentInvocationRecord, ArtifactRecord, EventSource, InvocationKind, InvocationState, RunEventRecord, RunRecord, RunStatus, TaskRecord, TaskStatus, WorkspaceAccess
from okcanvas_agent_runtime.domain.runs.transitions import require_run_transition, require_task_transition


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS schema_migration (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL,
    input_sha256 TEXT NOT NULL,
    protected_payload_ref TEXT,
    agent_definition_id TEXT NOT NULL,
    agent_definition_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS run (
    run_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES task(task_id),
    attempt INTEGER NOT NULL,
    status TEXT NOT NULL,
    agent_definition_id TEXT NOT NULL,
    agent_definition_version TEXT NOT NULL,
    session_ref TEXT,
    run_state_artifact_id TEXT,
    trace_id TEXT,
    codex_thread_id TEXT,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    UNIQUE(task_id, attempt)
);

CREATE TABLE IF NOT EXISTS run_event (
    run_id TEXT NOT NULL REFERENCES run(run_id),
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    payload_schema_version TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY(run_id, sequence)
);

CREATE INDEX IF NOT EXISTS idx_run_event_type ON run_event(run_id, event_type);

CREATE TABLE IF NOT EXISTS agent_invocation (
    invocation_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES run(run_id),
    root_invocation_id TEXT NOT NULL,
    parent_invocation_id TEXT REFERENCES agent_invocation(invocation_id),
    invocation_kind TEXT NOT NULL,
    state TEXT NOT NULL,
    agent_definition_id TEXT NOT NULL,
    agent_definition_version TEXT NOT NULL,
    agent_definition_sha256 TEXT NOT NULL,
    runtime_binding_sha256 TEXT NOT NULL,
    depth INTEGER NOT NULL,
    ordinal INTEGER NOT NULL,
    state_namespace TEXT NOT NULL UNIQUE,
    workspace_access TEXT NOT NULL,
    workspace_ref TEXT,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    UNIQUE(run_id, ordinal)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_invocation_root
ON agent_invocation(run_id) WHERE invocation_kind = 'ROOT';

CREATE INDEX IF NOT EXISTS idx_agent_invocation_parent
ON agent_invocation(parent_invocation_id, ordinal);

CREATE TABLE IF NOT EXISTS artifact (
    artifact_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES run(run_id),
    artifact_type TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    byte_length INTEGER NOT NULL,
    media_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    verified_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_artifact_run ON artifact(run_id, created_at);
"""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _identifier(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _canonical_payload(payload: dict[str, Any] | None) -> tuple[str, str]:
    encoded = json.dumps(
        payload or {},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return encoded, digest


def _file_integrity(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


class SQLiteProductStore:
    """SQLite implementation of the minimal OKCanvas product-state store."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.executescript(_SCHEMA_V1)
                row = connection.execute(
                    "SELECT 1 FROM schema_migration WHERE version = 1"
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO schema_migration(version, applied_at) VALUES(1, ?)",
                        (_utc_now(),),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
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

    def create_task(
        self,
        *,
        task_type: str,
        input_sha256: str,
        agent_definition_id: str,
        agent_definition_version: str,
        protected_payload_ref: str | None = None,
        task_id: str | None = None,
    ) -> TaskRecord:
        self._require_sha256(input_sha256, "input_sha256")
        task_id = task_id or _identifier("task")
        now = _utc_now()
        with self._connection() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO task(
                        task_id, task_type, status, input_sha256, protected_payload_ref,
                        agent_definition_id, agent_definition_version,
                        created_at, updated_at, completed_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        task_id,
                        task_type,
                        TaskStatus.READY.value,
                        input_sha256,
                        protected_payload_ref,
                        agent_definition_id,
                        agent_definition_version,
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateRecordError(
                    f"Task already exists: {task_id}", details={"task_id": task_id}
                ) from exc
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> TaskRecord:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM task WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"Task not found: {task_id}", details={"task_id": task_id}
            )
        return self._task_from_row(row)

    def list_tasks(
        self,
        *,
        status: TaskStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[TaskRecord], int]:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be 1..200")
        if offset < 0:
            raise ValueError("offset must be non-negative")
        where = " WHERE status = ?" if status is not None else ""
        params: tuple[Any, ...] = (status.value,) if status is not None else ()
        with self._connection() as connection:
            total = int(
                connection.execute(f"SELECT COUNT(*) FROM task{where}", params).fetchone()[0]
            )
            rows = connection.execute(
                f"SELECT * FROM task{where} "
                "ORDER BY created_at DESC, task_id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [self._task_from_row(row) for row in rows], total

    def task_status_counts(self) -> dict[str, int]:
        counts = {status.value: 0 for status in TaskStatus}
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS count FROM task GROUP BY status"
            ).fetchall()
        for row in rows:
            counts[str(row["status"])] = int(row["count"])
        return counts

    def transition_task(self, task_id: str, target: TaskStatus) -> TaskRecord:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT status FROM task WHERE task_id = ?", (task_id,)
                ).fetchone()
                if row is None:
                    raise RecordNotFoundError(
                        f"Task not found: {task_id}", details={"task_id": task_id}
                    )
                current = TaskStatus(row["status"])
                require_task_transition(current, target)
                now = _utc_now()
                completed_at = now if target in TERMINAL_TASK_STATUSES else None
                connection.execute(
                    "UPDATE task SET status = ?, updated_at = ?, completed_at = ? WHERE task_id = ?",
                    (target.value, now, completed_at, task_id),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self.get_task(task_id)

    def create_run(self, *, task_id: str, run_id: str | None = None) -> RunRecord:
        run_id = run_id or _identifier("run")
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                task = connection.execute(
                    "SELECT * FROM task WHERE task_id = ?", (task_id,)
                ).fetchone()
                if task is None:
                    raise RecordNotFoundError(
                        f"Task not found: {task_id}", details={"task_id": task_id}
                    )
                if TaskStatus(task["status"]) in TERMINAL_TASK_STATUSES:
                    raise IntegrityContractError(
                        "Cannot create a Run for a terminal Task",
                        details={"task_id": task_id, "status": task["status"]},
                    )
                attempt = int(
                    connection.execute(
                        "SELECT COALESCE(MAX(attempt), 0) + 1 AS next_attempt FROM run WHERE task_id = ?",
                        (task_id,),
                    ).fetchone()["next_attempt"]
                )
                now = _utc_now()
                connection.execute(
                    """
                    INSERT INTO run(
                        run_id, task_id, attempt, status,
                        agent_definition_id, agent_definition_version,
                        created_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        task_id,
                        attempt,
                        RunStatus.CREATED.value,
                        task["agent_definition_id"],
                        task["agent_definition_version"],
                        now,
                    ),
                )
                self._insert_event(
                    connection,
                    run_id=run_id,
                    event_type="run.created",
                    source=EventSource.RUNTIME,
                    payload={"attempt": attempt, "task_id": task_id},
                    payload_schema_version="okcanvas-run-created-v1",
                )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise DuplicateRecordError(
                    f"Run already exists: {run_id}", details={"run_id": run_id}
                ) from exc
            except Exception:
                connection.rollback()
                raise
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> RunRecord:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM run WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise RecordNotFoundError(f"Run not found: {run_id}", details={"run_id": run_id})
        return self._run_from_row(row)

    def list_runs(
        self,
        *,
        status: RunStatus | None = None,
        agent_definition_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RunRecord], int]:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be 1..200")
        if offset < 0:
            raise ValueError("offset must be non-negative")
        clauses: list[str] = []
        params: list[Any] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)
        if agent_definition_id is not None:
            clauses.append("agent_definition_id = ?")
            params.append(agent_definition_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connection() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM run{where}", tuple(params)
                ).fetchone()[0]
            )
            rows = connection.execute(
                f"SELECT * FROM run{where} "
                "ORDER BY created_at DESC, run_id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [self._run_from_row(row) for row in rows], total

    def run_status_counts(self) -> dict[str, int]:
        counts = {status.value: 0 for status in RunStatus}
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS count FROM run GROUP BY status"
            ).fetchall()
        for row in rows:
            counts[str(row["status"])] = int(row["count"])
        return counts

    def create_agent_invocation(
        self,
        *,
        run_id: str,
        parent_invocation_id: str | None,
        invocation_kind: InvocationKind,
        state: InvocationState,
        agent_definition_id: str,
        agent_definition_version: str,
        agent_definition_sha256: str,
        runtime_binding_sha256: str,
        depth: int,
        workspace_access: WorkspaceAccess,
        workspace_ref: str | None,
        invocation_id: str | None = None,
    ) -> AgentInvocationRecord:
        self._require_sha256(agent_definition_sha256, "agent_definition_sha256")
        self._require_sha256(runtime_binding_sha256, "runtime_binding_sha256")
        if depth < 0:
            raise IntegrityContractError("Invocation depth must be non-negative")
        if invocation_kind is InvocationKind.ROOT:
            if parent_invocation_id is not None or depth != 0:
                raise IntegrityContractError("Root invocation cannot have a parent or positive depth")
            if state is not InvocationState.RUNNING:
                raise IntegrityContractError("Root invocation must begin RUNNING")
        else:
            if not parent_invocation_id or depth < 1:
                raise IntegrityContractError("Child invocation requires a parent and positive depth")
            if state is not InvocationState.PLANNED:
                raise IntegrityContractError("STEP040 child invocation must begin PLANNED")
        if workspace_access is WorkspaceAccess.NONE and workspace_ref is not None:
            raise IntegrityContractError("workspace_access=none cannot have a workspace reference")
        invocation_id = invocation_id or _identifier("invocation")
        now = _utc_now()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                if not self._run_exists(connection, run_id):
                    raise RecordNotFoundError(
                        f"Run not found: {run_id}", details={"run_id": run_id}
                    )
                root_invocation_id = invocation_id
                if parent_invocation_id is not None:
                    parent = connection.execute(
                        "SELECT * FROM agent_invocation WHERE invocation_id = ?",
                        (parent_invocation_id,),
                    ).fetchone()
                    if parent is None:
                        raise RecordNotFoundError(
                            f"Parent invocation not found: {parent_invocation_id}",
                            details={"invocation_id": parent_invocation_id},
                        )
                    if parent["run_id"] != run_id:
                        raise IntegrityContractError("Parent invocation belongs to another Run")
                    if int(parent["depth"]) + 1 != depth:
                        raise IntegrityContractError("Child invocation depth does not match its parent")
                    root_invocation_id = str(parent["root_invocation_id"])
                ordinal = int(
                    connection.execute(
                        "SELECT COALESCE(MAX(ordinal), -1) + 1 AS next_ordinal "
                        "FROM agent_invocation WHERE run_id = ?",
                        (run_id,),
                    ).fetchone()["next_ordinal"]
                )
                state_namespace = f"invocation:{invocation_id}"
                started_at = now if state is InvocationState.RUNNING else None
                connection.execute(
                    """
                    INSERT INTO agent_invocation(
                        invocation_id, run_id, root_invocation_id, parent_invocation_id,
                        invocation_kind, state, agent_definition_id, agent_definition_version,
                        agent_definition_sha256, runtime_binding_sha256, depth, ordinal,
                        state_namespace, workspace_access, workspace_ref,
                        input_tokens, output_tokens, total_tokens, created_at, started_at, completed_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, NULL)
                    """,
                    (
                        invocation_id, run_id, root_invocation_id, parent_invocation_id,
                        invocation_kind.value, state.value, agent_definition_id,
                        agent_definition_version, agent_definition_sha256, runtime_binding_sha256,
                        depth, ordinal, state_namespace, workspace_access.value, workspace_ref,
                        now, started_at,
                    ),
                )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise DuplicateRecordError(
                    "Invocation identity already exists or violates the Run scope",
                    details={"invocation_id": invocation_id, "run_id": run_id},
                ) from exc
            except Exception:
                connection.rollback()
                raise
        return self.get_agent_invocation(invocation_id)

    def get_agent_invocation(self, invocation_id: str) -> AgentInvocationRecord:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM agent_invocation WHERE invocation_id = ?",
                (invocation_id,),
            ).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"Agent invocation not found: {invocation_id}",
                details={"invocation_id": invocation_id},
            )
        return self._invocation_from_row(row)

    def list_agent_invocations(self, run_id: str) -> list[AgentInvocationRecord]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM agent_invocation WHERE run_id = ? ORDER BY ordinal ASC",
                (run_id,),
            ).fetchall()
        return [self._invocation_from_row(row) for row in rows]

    def transition_agent_invocation(
        self, invocation_id: str, target: InvocationState
    ) -> AgentInvocationRecord:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT state FROM agent_invocation WHERE invocation_id = ?",
                    (invocation_id,),
                ).fetchone()
                if row is None:
                    raise RecordNotFoundError(
                        f"Agent invocation not found: {invocation_id}",
                        details={"invocation_id": invocation_id},
                    )
                current = InvocationState(str(row["state"]))
                allowed = {
                    InvocationState.PLANNED: {InvocationState.RUNNING, InvocationState.CANCELLED},
                    InvocationState.RUNNING: {
                        InvocationState.SUCCEEDED, InvocationState.FAILED, InvocationState.CANCELLED
                    },
                    InvocationState.SUCCEEDED: set(),
                    InvocationState.FAILED: set(),
                    InvocationState.CANCELLED: set(),
                }
                if target not in allowed[current]:
                    raise IntegrityContractError(
                        f"Invalid invocation transition: {current.value} -> {target.value}"
                    )
                now = _utc_now()
                started_at = now if target is InvocationState.RUNNING else None
                completed_at = now if target in {
                    InvocationState.SUCCEEDED, InvocationState.FAILED, InvocationState.CANCELLED
                } else None
                connection.execute(
                    """
                    UPDATE agent_invocation
                    SET state = ?,
                        started_at = COALESCE(started_at, ?),
                        completed_at = ?
                    WHERE invocation_id = ?
                    """,
                    (target.value, started_at, completed_at, invocation_id),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self.get_agent_invocation(invocation_id)

    def update_agent_invocation_usage(
        self,
        invocation_id: str,
        *,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
    ) -> AgentInvocationRecord:
        if min(input_tokens, output_tokens, total_tokens) < 0:
            raise IntegrityContractError("Invocation usage must be non-negative")
        if input_tokens + output_tokens > total_tokens:
            raise IntegrityContractError("Invocation total tokens cannot be smaller than components")
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE agent_invocation
                SET input_tokens = ?, output_tokens = ?, total_tokens = ?
                WHERE invocation_id = ?
                """,
                (input_tokens, output_tokens, total_tokens, invocation_id),
            )
            if cursor.rowcount != 1:
                raise RecordNotFoundError(
                    f"Agent invocation not found: {invocation_id}",
                    details={"invocation_id": invocation_id},
                )
        return self.get_agent_invocation(invocation_id)

    def artifact_count(self) -> int:
        with self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM artifact").fetchone()[0])

    def transition_run(
        self,
        run_id: str,
        target: RunStatus,
        *,
        event_type: str,
        source: EventSource = EventSource.RUNTIME,
        payload: dict[str, Any] | None = None,
        payload_schema_version: str = "okcanvas-event-payload-v1",
    ) -> RunRecord:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT status FROM run WHERE run_id = ?", (run_id,)
                ).fetchone()
                if row is None:
                    raise RecordNotFoundError(
                        f"Run not found: {run_id}", details={"run_id": run_id}
                    )
                current = RunStatus(row["status"])
                require_run_transition(current, target)
                now = _utc_now()
                started_at = now if target is RunStatus.RUNNING and current is RunStatus.CREATED else None
                completed_at = now if target in TERMINAL_RUN_STATUSES else None
                connection.execute(
                    """
                    UPDATE run
                    SET status = ?,
                        started_at = COALESCE(started_at, ?),
                        completed_at = ?
                    WHERE run_id = ?
                    """,
                    (target.value, started_at, completed_at, run_id),
                )
                event_payload = dict(payload or {})
                event_payload.setdefault("from_status", current.value)
                event_payload.setdefault("to_status", target.value)
                self._insert_event(
                    connection,
                    run_id=run_id,
                    event_type=event_type,
                    source=source,
                    payload=event_payload,
                    payload_schema_version=payload_schema_version,
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self.get_run(run_id)

    def append_event(
        self,
        run_id: str,
        *,
        event_type: str,
        source: EventSource,
        payload: dict[str, Any] | None = None,
        payload_schema_version: str = "okcanvas-event-payload-v1",
        require_active_run: bool = False,
    ) -> RunEventRecord:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                exists = connection.execute(
                    "SELECT status FROM run WHERE run_id = ?", (run_id,)
                ).fetchone()
                if exists is None:
                    raise RecordNotFoundError(
                        f"Run not found: {run_id}", details={"run_id": run_id}
                    )
                if require_active_run and RunStatus(str(exists["status"])) in TERMINAL_RUN_STATUSES:
                    raise IntegrityContractError(
                        "Cannot append an active execution Event to a terminal Run",
                        details={"run_id": run_id, "event_type": event_type},
                    )
                event = self._insert_event(
                    connection,
                    run_id=run_id,
                    event_type=event_type,
                    source=source,
                    payload=payload,
                    payload_schema_version=payload_schema_version,
                )
                connection.commit()
                return event
            except Exception:
                connection.rollback()
                raise

    def list_events(self, run_id: str, *, after_sequence: int = 0) -> list[RunEventRecord]:
        with self._connection() as connection:
            exists = connection.execute("SELECT 1 FROM run WHERE run_id = ?", (run_id,)).fetchone()
            if exists is None:
                raise RecordNotFoundError(
                    f"Run not found: {run_id}", details={"run_id": run_id}
                )
            rows = connection.execute(
                """
                SELECT * FROM run_event
                WHERE run_id = ? AND sequence > ?
                ORDER BY sequence ASC
                """,
                (run_id, after_sequence),
            ).fetchall()
        return [self._event_from_row(row) for row in rows]

    def update_run_execution_metadata(
        self,
        run_id: str,
        *,
        trace_id: str | None,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
    ) -> RunRecord:
        values = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values.values()):
            raise IntegrityContractError(
                "Run token usage must contain non-negative integers", details=values
            )
        if trace_id is not None and (not isinstance(trace_id, str) or not trace_id.strip()):
            raise IntegrityContractError("trace_id must be a non-empty string or null")
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE run
                SET trace_id = ?, input_tokens = ?, output_tokens = ?, total_tokens = ?
                WHERE run_id = ? AND status IN ('CREATED', 'RUNNING', 'INTERRUPTED')
                """,
                (trace_id, input_tokens, output_tokens, total_tokens, run_id),
            )
            if cursor.rowcount != 1:
                row = connection.execute(
                    "SELECT status FROM run WHERE run_id = ?", (run_id,)
                ).fetchone()
                if row is None:
                    raise RecordNotFoundError(
                        f"Run not found: {run_id}", details={"run_id": run_id}
                    )
                raise IntegrityContractError(
                    "Cannot update execution metadata on a terminal Run",
                    details={"run_id": run_id, "status": str(row["status"])},
                )
        return self.get_run(run_id)

    def register_artifact(
        self,
        *,
        run_id: str,
        artifact_type: str,
        storage_ref: str,
        sha256: str,
        byte_length: int,
        media_type: str,
        artifact_id: str | None = None,
    ) -> ArtifactRecord:
        if not storage_ref.strip():
            raise ArtifactIntegrityError("Artifact storage reference is required")
        if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256):
            raise ArtifactIntegrityError("Artifact SHA-256 is invalid")
        if byte_length < 0:
            raise ArtifactIntegrityError("Artifact byte length is invalid")
        artifact_id = artifact_id or _identifier("artifact")
        now = _utc_now()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                run_row = connection.execute(
                    "SELECT status FROM run WHERE run_id = ?", (run_id,)
                ).fetchone()
                if run_row is None:
                    raise RecordNotFoundError(
                        f"Run not found: {run_id}", details={"run_id": run_id}
                    )
                if RunStatus(str(run_row["status"])) in TERMINAL_RUN_STATUSES:
                    raise ArtifactIntegrityError(
                        "Cannot register an Artifact for a terminal Run",
                        details={"run_id": run_id, "status": str(run_row["status"])},
                    )
                connection.execute(
                    """
                    INSERT INTO artifact(
                        artifact_id, run_id, artifact_type, storage_path,
                        sha256, byte_length, media_type, created_at, verified_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact_id,
                        run_id,
                        artifact_type,
                        storage_ref,
                        sha256,
                        byte_length,
                        media_type,
                        now,
                        now,
                    ),
                )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                if self._run_exists(connection, run_id):
                    raise DuplicateRecordError(
                        f"Artifact already exists: {artifact_id}",
                        details={"artifact_id": artifact_id},
                    ) from exc
                raise RecordNotFoundError(
                    f"Run not found: {run_id}", details={"run_id": run_id}
                ) from exc
            except Exception:
                connection.rollback()
                raise
        return self.get_artifact(artifact_id)

    def get_artifact(self, artifact_id: str) -> ArtifactRecord:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM artifact WHERE artifact_id = ?", (artifact_id,)
            ).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"Artifact not found: {artifact_id}", details={"artifact_id": artifact_id}
            )
        return self._artifact_from_row(row)

    def list_artifacts(self, run_id: str) -> list[ArtifactRecord]:
        with self._connection() as connection:
            if not self._run_exists(connection, run_id):
                raise RecordNotFoundError(
                    f"Run not found: {run_id}", details={"run_id": run_id}
                )
            rows = connection.execute(
                "SELECT * FROM artifact WHERE run_id = ? ORDER BY created_at ASC, artifact_id ASC",
                (run_id,),
            ).fetchall()
        return [self._artifact_from_row(row) for row in rows]

    def verify_artifact(self, artifact_id: str) -> ArtifactRecord:
        artifact = self.get_artifact(artifact_id)
        with self._connection() as connection:
            connection.execute(
                "UPDATE artifact SET verified_at = ? WHERE artifact_id = ?",
                (_utc_now(), artifact_id),
            )
        return self.get_artifact(artifact_id)

    def schema_versions(self) -> list[int]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT version FROM schema_migration ORDER BY version"
            ).fetchall()
        return [int(row["version"]) for row in rows]

    def _insert_event(
        self,
        connection: sqlite3.Connection,
        *,
        run_id: str,
        event_type: str,
        source: EventSource,
        payload: dict[str, Any] | None,
        payload_schema_version: str,
    ) -> RunEventRecord:
        sequence = int(
            connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence FROM run_event WHERE run_id = ?",
                (run_id,),
            ).fetchone()["next_sequence"]
        )
        payload_json, payload_sha256 = _canonical_payload(payload)
        occurred_at = _utc_now()
        connection.execute(
            """
            INSERT INTO run_event(
                run_id, sequence, event_type, source, occurred_at,
                payload_schema_version, payload_sha256, payload_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                sequence,
                event_type,
                source.value,
                occurred_at,
                payload_schema_version,
                payload_sha256,
                payload_json,
            ),
        )
        return RunEventRecord(
            run_id=run_id,
            sequence=sequence,
            event_type=event_type,
            source=source,
            occurred_at=occurred_at,
            payload_schema_version=payload_schema_version,
            payload_sha256=payload_sha256,
            payload=json.loads(payload_json),
        )

    @staticmethod
    def _require_sha256(value: str, field: str) -> None:
        if not _SHA256_RE.fullmatch(value):
            raise IntegrityContractError(
                f"{field} must be a lowercase SHA-256 hex digest",
                details={"field": field},
            )

    @staticmethod
    def _run_exists(connection: sqlite3.Connection, run_id: str) -> bool:
        return connection.execute("SELECT 1 FROM run WHERE run_id = ?", (run_id,)).fetchone() is not None

    @staticmethod
    def _task_from_row(row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            task_id=row["task_id"],
            task_type=row["task_type"],
            status=TaskStatus(row["status"]),
            input_sha256=row["input_sha256"],
            protected_payload_ref=row["protected_payload_ref"],
            agent_definition_id=row["agent_definition_id"],
            agent_definition_version=row["agent_definition_version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
        )

    @staticmethod
    def _run_from_row(row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            run_id=row["run_id"],
            task_id=row["task_id"],
            attempt=int(row["attempt"]),
            status=RunStatus(row["status"]),
            agent_definition_id=row["agent_definition_id"],
            agent_definition_version=row["agent_definition_version"],
            session_ref=row["session_ref"],
            run_state_artifact_id=row["run_state_artifact_id"],
            trace_id=row["trace_id"],
            codex_thread_id=row["codex_thread_id"],
            input_tokens=int(row["input_tokens"]),
            output_tokens=int(row["output_tokens"]),
            total_tokens=int(row["total_tokens"]),
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> RunEventRecord:
        return RunEventRecord(
            run_id=row["run_id"],
            sequence=int(row["sequence"]),
            event_type=row["event_type"],
            source=EventSource(row["source"]),
            occurred_at=row["occurred_at"],
            payload_schema_version=row["payload_schema_version"],
            payload_sha256=row["payload_sha256"],
            payload=json.loads(row["payload_json"]),
        )

    @staticmethod
    def _invocation_from_row(row: sqlite3.Row) -> AgentInvocationRecord:
        return AgentInvocationRecord(
            invocation_id=row["invocation_id"],
            run_id=row["run_id"],
            root_invocation_id=row["root_invocation_id"],
            parent_invocation_id=row["parent_invocation_id"],
            invocation_kind=InvocationKind(row["invocation_kind"]),
            state=InvocationState(row["state"]),
            agent_definition_id=row["agent_definition_id"],
            agent_definition_version=row["agent_definition_version"],
            agent_definition_sha256=row["agent_definition_sha256"],
            runtime_binding_sha256=row["runtime_binding_sha256"],
            depth=int(row["depth"]),
            ordinal=int(row["ordinal"]),
            state_namespace=row["state_namespace"],
            workspace_access=WorkspaceAccess(row["workspace_access"]),
            workspace_ref=row["workspace_ref"],
            input_tokens=int(row["input_tokens"]),
            output_tokens=int(row["output_tokens"]),
            total_tokens=int(row["total_tokens"]),
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )

    @staticmethod
    def _artifact_from_row(row: sqlite3.Row) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=row["artifact_id"],
            run_id=row["run_id"],
            artifact_type=row["artifact_type"],
            storage_path=row["storage_path"],
            sha256=row["sha256"],
            byte_length=int(row["byte_length"]),
            media_type=row["media_type"],
            created_at=row["created_at"],
            verified_at=row["verified_at"],
        )
