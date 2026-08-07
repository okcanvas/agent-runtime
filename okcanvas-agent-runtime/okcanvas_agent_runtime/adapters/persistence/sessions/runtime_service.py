from __future__ import annotations

import asyncio
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from okcanvas_agent_runtime.agent.definitions import AgentDefinition

from okcanvas_agent_runtime.domain.sessions.compaction import BoundedEncryptedCompactionSession, CompactionEventSink
from okcanvas_agent_runtime.adapters.storage.session_history import SessionHistoryKey, StrictEncryptedSession
from okcanvas_agent_runtime.domain.sessions.errors import SessionBusyError, SessionConfigurationError, SessionIntegrityError, SessionNotFound, SessionPolicyError, SessionStateError
from okcanvas_agent_runtime.domain.sessions.models import ProductSessionRecord, ProductSessionState, SQLiteSessionPolicy
from okcanvas_agent_runtime.adapters.persistence.sessions.rotation import SessionKeyRotationResult, SQLiteSessionHistoryRotator
from okcanvas_agent_runtime.domain.sessions.rotation_policy import SQLiteSessionKeyRotationPolicy

_SCHEMA = """
CREATE TABLE IF NOT EXISTS product_session (
    session_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    agent_definition_id TEXT NOT NULL,
    agent_definition_version TEXT NOT NULL,
    agent_definition_sha256 TEXT NOT NULL,
    runtime_binding_sha256 TEXT NOT NULL,
    history_encryption_key_id TEXT,
    active_run_id TEXT,
    turn_count INTEGER NOT NULL DEFAULT 0,
    item_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    cleared_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_product_session_updated
ON product_session(updated_at DESC, session_id DESC);
CREATE TABLE IF NOT EXISTS product_session_key_rotation (
    session_id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL UNIQUE,
    source_key_id TEXT NOT NULL,
    target_key_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES product_session(session_id)
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class SQLiteSessionRuntimeService:
    def __init__(
        self,
        root: str | Path,
        policy: SQLiteSessionPolicy,
        history_key: SessionHistoryKey | None = None,
        *,
        previous_history_key: SessionHistoryKey | None = None,
        key_rotation_policy: SQLiteSessionKeyRotationPolicy | None = None,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.policy = policy
        self.history_key = history_key
        self.previous_history_key = previous_history_key
        self.key_rotation_policy = key_rotation_policy
        self.catalog_db = self.root / "catalog.sqlite3"
        self.history_db = self.root / "history.sqlite3"

    def _validate_database_path(self, path: Path) -> None:
        if path.parent != self.root:
            raise SessionIntegrityError("Session database path escaped the configured root")
        if path.exists() and (path.is_symlink() or not path.is_file()):
            raise SessionIntegrityError("Session database path is unsafe")

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink() or not self.root.is_dir():
            raise SessionIntegrityError("Session root must be a real directory")
        self._validate_database_path(self.catalog_db)
        conn = sqlite3.connect(self.catalog_db, timeout=15, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=15000")
        try:
            yield conn
        finally:
            conn.close()

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink() or not self.root.is_dir():
            raise SessionIntegrityError("Session root must be a real directory")
        with self._connection() as conn:
            conn.executescript(_SCHEMA)
            columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info(product_session)")}
            if "history_encryption_key_id" not in columns:
                conn.execute("ALTER TABLE product_session ADD COLUMN history_encryption_key_id TEXT")

    def _require_history_key(self) -> SessionHistoryKey:
        if not self.policy.encryption_enabled:
            raise SessionConfigurationError("Session history encryption policy is not enabled")
        if self.history_key is None:
            raise SessionConfigurationError(
                "OKCANVAS_SESSION_HISTORY_KEY is required for SQLite Session operations"
            )
        return self.history_key

    def _validate_record_key(self, record: ProductSessionRecord) -> None:
        key = self._require_history_key()
        if record.history_encryption_key_id is None:
            raise SessionIntegrityError(
                "Session was created before strict history encryption and must be cleared and recreated"
            )
        if record.history_encryption_key_id != key.key_id:
            raise SessionIntegrityError("Session history encryption key ID changed")

    def create(self, *, definition: AgentDefinition, runtime_binding_sha256: str) -> ProductSessionRecord:
        if definition.session_mode != self.policy.session_mode:
            raise SessionStateError("Agent does not use the configured SQLite Session mode")
        session_handoff_mode = (
            len(definition.handoffs) == 1
            and not definition.tools
            and not definition.mcp_servers
            and not definition.agent_tools
            and not definition.guardrails
            and definition.workspace_access == "none"
        )
        session_mcp_mode = (
            len(definition.mcp_servers) == 1
            and not definition.tools
            and not definition.handoffs
            and not definition.agent_tools
            and not definition.guardrails
            and definition.workspace_access == "none"
        )
        session_agent_tool_mode = (
            len(definition.agent_tools) == 1
            and not definition.tools
            and not definition.mcp_servers
            and not definition.handoffs
            and not definition.guardrails
            and definition.workspace_access == "none"
        )
        if (
            (definition.mcp_servers and not session_mcp_mode)
            or (definition.agent_tools and not session_agent_tool_mode)
            or (definition.handoffs and not session_handoff_mode)
        ):
            raise SessionStateError("SQLite Session Agent has an unsupported child or MCP composition")
        history_key = self._require_history_key()
        session_id = f"session_{uuid.uuid4().hex}"
        now = _now()
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """INSERT INTO product_session(
                    session_id,state,agent_definition_id,agent_definition_version,
                    agent_definition_sha256,runtime_binding_sha256,history_encryption_key_id,active_run_id,
                    turn_count,item_count,created_at,updated_at,cleared_at
                ) VALUES(?,?,?,?,?,?,?,NULL,0,0,?,?,NULL)""",
                (session_id, ProductSessionState.ACTIVE.value, definition.agent_id,
                 definition.version, definition.definition_sha256, runtime_binding_sha256,
                 history_key.key_id, now, now),
            )
            conn.commit()
        return self.get(session_id)

    def get(self, session_id: str) -> ProductSessionRecord:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM product_session WHERE session_id=?", (session_id,)).fetchone()
        if row is None:
            raise SessionNotFound(f"Session not found: {session_id}")
        return self._from_row(row)

    def list(self, *, limit: int = 100) -> tuple[ProductSessionRecord, ...]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM product_session ORDER BY updated_at DESC, session_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(self._from_row(row) for row in rows)

    def validate_binding(self, *, session_id: str, definition: AgentDefinition, runtime_binding_sha256: str) -> ProductSessionRecord:
        record = self.get(session_id)
        if record.state is not ProductSessionState.ACTIVE:
            raise SessionStateError("Session is not active")
        self._validate_record_key(record)
        if (
            record.agent_definition_id != definition.agent_id
            or record.agent_definition_version != definition.version
            or record.agent_definition_sha256 != definition.definition_sha256
            or record.runtime_binding_sha256 != runtime_binding_sha256
        ):
            raise SessionIntegrityError("Session Agent or Runtime binding changed")
        return record

    def acquire_turn(self, *, session_id: str, run_id: str, definition: AgentDefinition, runtime_binding_sha256: str) -> ProductSessionRecord:
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM product_session WHERE session_id=?", (session_id,)).fetchone()
            if row is None:
                conn.rollback()
                raise SessionNotFound(f"Session not found: {session_id}")
            record = self._from_row(row)
            if record.state is not ProductSessionState.ACTIVE:
                conn.rollback()
                raise SessionStateError("Session is not active")
            if record.active_run_id is not None and record.active_run_id != run_id:
                conn.rollback()
                raise SessionBusyError("Session already has an active Turn")
            try:
                self._validate_record_key(record)
            except Exception:
                conn.rollback()
                raise
            if (
                self.policy.compaction_enabled
                and record.item_count > self.policy.compaction_max_input_items
            ):
                conn.rollback()
                raise SessionStateError(
                    "Session history exceeded the bounded compaction recovery limit and must be cleared"
                )
            if (
                record.agent_definition_id != definition.agent_id
                or record.agent_definition_version != definition.version
                or record.agent_definition_sha256 != definition.definition_sha256
                or record.runtime_binding_sha256 != runtime_binding_sha256
            ):
                conn.rollback()
                raise SessionIntegrityError("Session Agent or Runtime binding changed")
            now = _now()
            conn.execute(
                "UPDATE product_session SET active_run_id=?, updated_at=? WHERE session_id=?",
                (run_id, now, session_id),
            )
            conn.commit()
        return self.get(session_id)

    def release_turn(
        self, *, session_id: str, run_id: str, succeeded: bool | None = None,
        committed: bool | None = None, item_count: int
    ) -> ProductSessionRecord:
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM product_session WHERE session_id=?", (session_id,)).fetchone()
            if row is None:
                conn.rollback()
                raise SessionNotFound(f"Session not found: {session_id}")
            record = self._from_row(row)
            if record.active_run_id != run_id:
                conn.rollback()
                raise SessionIntegrityError("Session active Turn does not match the Product Run")
            try:
                self._validate_record_key(record)
            except Exception:
                conn.rollback()
                raise
            should_commit = committed if committed is not None else bool(succeeded)
            turn_count = int(row["turn_count"]) + (1 if should_commit else 0)
            now = _now()
            conn.execute(
                """UPDATE product_session
                   SET active_run_id=NULL, turn_count=?, item_count=?, updated_at=?
                   WHERE session_id=?""",
                (turn_count, max(0, int(item_count)), now, session_id),
            )
            conn.commit()
        return self.get(session_id)


    def assert_active_turn(self, *, session_id: str, run_id: str) -> ProductSessionRecord:
        record = self.get(session_id)
        if record.state is not ProductSessionState.ACTIVE or record.active_run_id != run_id:
            raise SessionIntegrityError("Session active Turn does not match the Product Run")
        self._validate_record_key(record)
        return record

    def update_active_item_count(
        self, *, session_id: str, run_id: str, item_count: int
    ) -> ProductSessionRecord:
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM product_session WHERE session_id=?",
                (session_id,),
            ).fetchone()
            if row is None:
                conn.rollback()
                raise SessionNotFound(f"Session not found: {session_id}")
            record = self._from_row(row)
            if record.state is not ProductSessionState.ACTIVE or record.active_run_id != run_id:
                conn.rollback()
                raise SessionIntegrityError("Session active Turn does not match the Product Run")
            try:
                self._validate_record_key(record)
            except Exception:
                conn.rollback()
                raise
            conn.execute(
                "UPDATE product_session SET item_count=?, updated_at=? WHERE session_id=?",
                (max(0, int(item_count)), _now(), session_id),
            )
            conn.commit()
        return self.get(session_id)

    async def rollback_to_item_count(
        self, *, session_id: str, expected_item_count: int
    ) -> int:
        session = self.encrypted_sdk_session(session_id)
        try:
            items = await session.get_items()
            if len(items) < expected_item_count:
                raise SessionIntegrityError("Session history is shorter than the rollback boundary")
            while len(items) > expected_item_count:
                removed = await session.pop_item()
                if removed is None:
                    raise SessionIntegrityError("Session rollback could not remove a persisted item")
                items.pop()
            return len(items)
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()

    def raw_sdk_session(self, session_id: str):
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink() or not self.root.is_dir():
            raise SessionIntegrityError("Session root must be a real directory")
        self._validate_database_path(self.history_db)
        try:
            from agents import SQLiteSession
        except Exception as exc:
            raise SessionIntegrityError("Installed SDK SQLiteSession is unavailable") from exc
        return SQLiteSession(session_id, db_path=self.history_db)

    def encrypted_sdk_session(self, session_id: str):
        record = self.get(session_id)
        self._validate_record_key(record)
        key = self._require_history_key()
        return StrictEncryptedSession(
            session_id=session_id,
            underlying_session=self.raw_sdk_session(session_id),
            key=key,
        )

    def sdk_session(self, session_id: str):
        return self.encrypted_sdk_session(session_id)

    def _compaction_session(
        self,
        session_id: str,
        *,
        compaction_api_key: str | None,
        compaction_event_sink: CompactionEventSink | None,
    ) -> BoundedEncryptedCompactionSession:
        encrypted = self.encrypted_sdk_session(session_id)

        def compactor_factory():
            if not compaction_api_key or not compaction_api_key.strip():
                raise SessionConfigurationError(
                    "OPENAI_API_KEY is required when Session compaction threshold is reached"
                )
            try:
                from agents import OpenAIResponsesCompactionSession
                from openai import AsyncOpenAI
            except Exception as exc:
                raise SessionConfigurationError(
                    "Installed SDK compaction support is unavailable"
                ) from exc
            client = AsyncOpenAI(
                api_key=compaction_api_key,
                base_url="https://api.openai.com/v1",
                max_retries=0,
            )
            return OpenAIResponsesCompactionSession(
                session_id=session_id,
                underlying_session=encrypted,
                client=client,
                model=self.policy.compaction_model,
                compaction_mode="input",
                should_trigger_compaction=lambda context: len(
                    context["compaction_candidate_items"]
                ) >= self.policy.compaction_trigger_candidate_items,
            )

        return BoundedEncryptedCompactionSession(
            session_id=session_id,
            encrypted_storage_session=encrypted,
            compactor_factory=compactor_factory,
            policy=self.policy,
            event_sink=compaction_event_sink,
        )

    async def compact_after_committed_turn(
        self,
        *,
        session_id: str,
        run_id: str,
        compaction_api_key: str | None,
        compaction_event_sink: CompactionEventSink | None = None,
    ) -> bool:
        """Attempt bounded compaction after the Product Turn has committed.

        A short database-backed lease reuses ``active_run_id`` with the same Product Run
        while that Run is still RUNNING. This prevents a new Turn or clear operation from
        racing with replacement of encrypted history. Routine compaction failures restore
        the previous history and do not reverse the committed Turn.
        """

        if not self.policy.compaction_enabled:
            return False
        lease_acquired = False
        session: BoundedEncryptedCompactionSession | None = None
        try:
            with self._connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT * FROM product_session WHERE session_id=?", (session_id,)
                ).fetchone()
                if row is None:
                    conn.rollback()
                    raise SessionNotFound(f"Session not found: {session_id}")
                record = self._from_row(row)
                if record.state is not ProductSessionState.ACTIVE:
                    conn.rollback()
                    raise SessionStateError("Session compaction requires an active Session")
                if record.active_run_id is not None:
                    conn.rollback()
                    raise SessionBusyError("Session already has an active Turn or compaction lease")
                self._validate_record_key(record)
                updated = conn.execute(
                    "UPDATE product_session SET active_run_id=?, updated_at=? "
                    "WHERE session_id=? AND active_run_id IS NULL",
                    (run_id, _now(), session_id),
                ).rowcount
                if updated != 1:
                    conn.rollback()
                    raise SessionBusyError("Session compaction lease could not be acquired")
                conn.commit()
                lease_acquired = True

            session = self._compaction_session(
                session_id,
                compaction_api_key=compaction_api_key,
                compaction_event_sink=compaction_event_sink,
            )
            compacted = await session.run_compaction({"store": False})
            if not compacted:
                return False

            item_count = len(await session.get_items())
            now = _now()
            with self._connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT * FROM product_session WHERE session_id=?", (session_id,)
                ).fetchone()
                if row is None:
                    conn.rollback()
                    raise SessionNotFound(f"Session not found: {session_id}")
                current = self._from_row(row)
                if (
                    current.state is not ProductSessionState.ACTIVE
                    or current.active_run_id != run_id
                ):
                    conn.rollback()
                    raise SessionIntegrityError("Session compaction lease changed unexpectedly")
                self._validate_record_key(current)
                conn.execute(
                    "UPDATE product_session SET active_run_id=NULL, item_count=?, updated_at=? "
                    "WHERE session_id=? AND active_run_id=?",
                    (item_count, now, session_id, run_id),
                )
                conn.commit()
                lease_acquired = False

            if compaction_event_sink is not None:
                await compaction_event_sink(
                    "session.compaction.completed",
                    {
                        "session_id": session_id,
                        "compaction_policy_id": self.policy.policy_id,
                        "compaction_policy_sha256": self.policy.policy_sha256,
                        "compaction_mode": self.policy.compaction_mode,
                        "compaction_provider": self.policy.compaction_provider,
                        "compaction_api": self.policy.compaction_api,
                        "compaction_model": self.policy.compaction_model,
                        "output_item_count": item_count,
                        "provider_request_count": 1,
                        "provider_token_usage_recorded": False,
                        "history_persisted_in_product_events": False,
                    },
                )
            return True
        except Exception:
            return False
        finally:
            if lease_acquired:
                try:
                    with self._connection() as conn:
                        conn.execute("BEGIN IMMEDIATE")
                        conn.execute(
                            "UPDATE product_session SET active_run_id=NULL, updated_at=? "
                            "WHERE session_id=? AND active_run_id=?",
                            (_now(), session_id, run_id),
                        )
                        conn.commit()
                except Exception:
                    pass
            if session is not None:
                session.close()

    def _require_key_rotation_policy(self) -> SQLiteSessionKeyRotationPolicy:
        if self.key_rotation_policy is None:
            raise SessionConfigurationError("SQLite Session key rotation policy is unavailable")
        return self.key_rotation_policy

    def _rotation_row(self, conn: sqlite3.Connection, session_id: str) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT * FROM product_session_key_rotation WHERE session_id=?",
            (session_id,),
        ).fetchone()

    def _prepare_key_rotation(self, session_id: str) -> tuple[str | None, str, str, bool, bool]:
        policy = self._require_key_rotation_policy()
        if policy.mode != "EXPLICIT_SINGLE_SESSION":
            raise SessionPolicyError("Unsupported Session key rotation mode")
        target_key = self._require_history_key()
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM product_session WHERE session_id=?", (session_id,)
            ).fetchone()
            if row is None:
                conn.rollback()
                raise SessionNotFound(f"Session not found: {session_id}")
            record = self._from_row(row)
            if record.state is not ProductSessionState.ACTIVE:
                conn.rollback()
                raise SessionStateError("Session is not active")
            rotation = self._rotation_row(conn, session_id)
            if rotation is not None:
                operation_id = str(rotation["operation_id"])
                if record.active_run_id != operation_id:
                    conn.rollback()
                    raise SessionIntegrityError("Session key rotation lease is inconsistent")
                source_key_id = str(rotation["source_key_id"])
                target_key_id = str(rotation["target_key_id"])
                if target_key_id != target_key.key_id:
                    conn.rollback()
                    raise SessionIntegrityError("Session key rotation target key changed")
                conn.commit()
                return operation_id, source_key_id, target_key_id, True, False
            if record.active_run_id is not None:
                conn.rollback()
                raise SessionBusyError("Session already has an active Turn or maintenance lease")
            if record.history_encryption_key_id is None:
                conn.rollback()
                raise SessionIntegrityError(
                    "Session was created before strict history encryption and must be cleared and recreated"
                )
            if record.history_encryption_key_id == target_key.key_id:
                conn.commit()
                return None, target_key.key_id, target_key.key_id, False, True
            source_key = self.previous_history_key
            if source_key is None:
                conn.rollback()
                raise SessionConfigurationError(
                    "OKCANVAS_SESSION_HISTORY_PREVIOUS_KEY is required for key rotation"
                )
            if source_key.key_id == target_key.key_id:
                conn.rollback()
                raise SessionConfigurationError(
                    "Current and previous Session history keys must be distinct"
                )
            if record.history_encryption_key_id != source_key.key_id:
                conn.rollback()
                raise SessionIntegrityError(
                    "Session history encryption key ID does not match the configured previous key"
                )
            operation_id = f"session_rotation_{uuid.uuid4().hex}"
            now = _now()
            conn.execute(
                "INSERT INTO product_session_key_rotation("
                "session_id,operation_id,source_key_id,target_key_id,started_at,updated_at"
                ") VALUES(?,?,?,?,?,?)",
                (session_id, operation_id, source_key.key_id, target_key.key_id, now, now),
            )
            conn.execute(
                "UPDATE product_session SET active_run_id=?, updated_at=? WHERE session_id=?",
                (operation_id, now, session_id),
            )
            conn.commit()
        return operation_id, source_key.key_id, target_key.key_id, False, False

    def _finalize_key_rotation(
        self, *, session_id: str, operation_id: str, target_key_id: str, item_count: int
    ) -> None:
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM product_session WHERE session_id=?", (session_id,)
            ).fetchone()
            rotation = self._rotation_row(conn, session_id)
            if row is None:
                conn.rollback()
                raise SessionNotFound(f"Session not found: {session_id}")
            if rotation is None:
                if (
                    row["active_run_id"] is None
                    and str(row["history_encryption_key_id"] or "") == target_key_id
                    and int(row["item_count"]) == item_count
                ):
                    conn.commit()
                    return
                conn.rollback()
                raise SessionIntegrityError("Session key rotation record disappeared")
            if str(row["active_run_id"] or "") != operation_id:
                conn.rollback()
                raise SessionIntegrityError("Session key rotation lease changed unexpectedly")
            if str(rotation["operation_id"]) != operation_id:
                conn.rollback()
                raise SessionIntegrityError("Session key rotation operation changed unexpectedly")
            if str(rotation["target_key_id"]) != target_key_id:
                conn.rollback()
                raise SessionIntegrityError("Session key rotation target changed unexpectedly")
            now = _now()
            conn.execute(
                "UPDATE product_session SET history_encryption_key_id=?, active_run_id=NULL, "
                "item_count=?, updated_at=? WHERE session_id=?",
                (target_key_id, item_count, now, session_id),
            )
            conn.execute(
                "DELETE FROM product_session_key_rotation WHERE session_id=?", (session_id,)
            )
            conn.commit()

    def _rotate_history_key_sync(self, session_id: str) -> SessionKeyRotationResult:
        operation_id, source_key_id, target_key_id, resumed, already_current = (
            self._prepare_key_rotation(session_id)
        )
        record = self.get(session_id)
        if already_current:
            return SessionKeyRotationResult(
                session_id=session_id,
                operation_id=None,
                source_key_id=source_key_id,
                target_key_id=target_key_id,
                item_count=record.item_count,
                resumed=False,
                already_current=True,
            )
        if operation_id is None:
            raise SessionIntegrityError("Session key rotation operation was not created")
        target_key = self._require_history_key()
        source_key = self.previous_history_key
        if source_key is not None and source_key.key_id != source_key_id:
            source_key = None
        outcome = SQLiteSessionHistoryRotator(
            history_db=self.history_db,
            policy=self._require_key_rotation_policy(),
        ).rotate(
            session_id=session_id,
            source_key_id=source_key_id,
            source_key=source_key,
            target_key=target_key,
        )
        self._finalize_key_rotation(
            session_id=session_id,
            operation_id=operation_id,
            target_key_id=target_key_id,
            item_count=outcome.item_count,
        )
        return SessionKeyRotationResult(
            session_id=session_id,
            operation_id=operation_id,
            source_key_id=source_key_id,
            target_key_id=target_key_id,
            item_count=outcome.item_count,
            resumed=resumed or outcome.observed_mode == "ALREADY_TARGET",
            already_current=False,
        )

    async def rotate_history_key(self, session_id: str) -> SessionKeyRotationResult:
        return await asyncio.to_thread(self._rotate_history_key_sync, session_id)

    async def count_items(self, session_id: str) -> int:
        session = self.encrypted_sdk_session(session_id)
        try:
            return len(await session.get_items())
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()

    async def clear(self, session_id: str) -> ProductSessionRecord:
        rotation_clear = False
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM product_session WHERE session_id=?", (session_id,)).fetchone()
            if row is None:
                conn.rollback()
                raise SessionNotFound(f"Session not found: {session_id}")
            record = self._from_row(row)
            if record.state is ProductSessionState.CLEARED:
                conn.commit()
                return record
            if record.state is ProductSessionState.CLEARING:
                conn.rollback()
                raise SessionBusyError("Session clear is already in progress")
            rotation = self._rotation_row(conn, session_id)
            rotation_clear = (
                rotation is not None
                and record.active_run_id == str(rotation["operation_id"])
                and self.key_rotation_policy is not None
                and self.key_rotation_policy.clear_incomplete_rotation_without_decrypt
            )
            if record.active_run_id is not None and not rotation_clear:
                conn.rollback()
                raise SessionBusyError("Active Session Turn cannot be cleared")
            now = _now()
            conn.execute(
                "UPDATE product_session SET state=?, updated_at=? WHERE session_id=?",
                (ProductSessionState.CLEARING.value, now, session_id),
            )
            conn.commit()

        session = None
        try:
            if rotation_clear:
                await asyncio.to_thread(
                    SQLiteSessionHistoryRotator(
                        history_db=self.history_db,
                        policy=self._require_key_rotation_policy(),
                    ).clear_session,
                    session_id,
                )
            else:
                session = self.raw_sdk_session(session_id)
                await session.clear_session()
        except BaseException:
            with self._connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "UPDATE product_session SET state=?, updated_at=? WHERE session_id=? AND state=?",
                    (ProductSessionState.ACTIVE.value, _now(), session_id, ProductSessionState.CLEARING.value),
                )
                conn.commit()
            raise
        finally:
            if session is not None:
                close = getattr(session, "close", None)
                if callable(close):
                    close()

        now = _now()
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM product_session WHERE session_id=?", (session_id,)).fetchone()
            if row is None:
                conn.rollback()
                raise SessionNotFound(f"Session not found: {session_id}")
            rotation = self._rotation_row(conn, session_id)
            expected_rotation_id = str(rotation["operation_id"]) if rotation is not None else None
            if row["state"] != ProductSessionState.CLEARING.value:
                conn.rollback()
                raise SessionIntegrityError("Session clear state changed unexpectedly")
            if row["active_run_id"] not in (None, expected_rotation_id):
                conn.rollback()
                raise SessionIntegrityError("Session clear maintenance lease changed unexpectedly")
            conn.execute(
                """UPDATE product_session SET state=?, active_run_id=NULL, item_count=0,
                   updated_at=?, cleared_at=? WHERE session_id=?""",
                (ProductSessionState.CLEARED.value, now, now, session_id),
            )
            if rotation is not None:
                conn.execute(
                    "DELETE FROM product_session_key_rotation WHERE session_id=?", (session_id,)
                )
            conn.commit()
        return self.get(session_id)

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ProductSessionRecord:
        return ProductSessionRecord(
            session_id=str(row["session_id"]),
            state=ProductSessionState(str(row["state"])),
            agent_definition_id=str(row["agent_definition_id"]),
            agent_definition_version=str(row["agent_definition_version"]),
            agent_definition_sha256=str(row["agent_definition_sha256"]),
            runtime_binding_sha256=str(row["runtime_binding_sha256"]),
            history_encryption_key_id=(
                str(row["history_encryption_key_id"])
                if row["history_encryption_key_id"] is not None
                else None
            ),
            active_run_id=str(row["active_run_id"]) if row["active_run_id"] else None,
            turn_count=int(row["turn_count"]),
            item_count=int(row["item_count"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            cleared_at=str(row["cleared_at"]) if row["cleared_at"] else None,
        )
