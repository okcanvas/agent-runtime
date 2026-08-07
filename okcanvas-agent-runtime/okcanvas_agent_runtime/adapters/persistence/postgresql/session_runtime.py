from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from okcanvas_agent_runtime.adapters.persistence.postgresql.driver import (
    ConnectFactory,
    PostgreSQLConnectionAdapter,
    PostgreSQLConnectionSettings,
    postgresql_connection,
)
from okcanvas_agent_runtime.adapters.persistence.sessions.runtime_service import (
    SQLiteSessionRuntimeService,
)
from okcanvas_agent_runtime.adapters.storage.session_history import SessionHistoryKey
from okcanvas_agent_runtime.domain.sessions.errors import SessionIntegrityError
from okcanvas_agent_runtime.domain.sessions.models import SQLiteSessionPolicy
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


class PostgreSQLSessionMetadataRuntimeService(SQLiteSessionRuntimeService):
    """PostgreSQL Session metadata with encrypted local SQLite SDK history.

    Session lifecycle, active-turn fencing, counts and key-rotation checkpoints
    are PostgreSQL-owned. Model input history stays in the existing encrypted
    local SQLite SDK store until a dedicated distributed history boundary exists.
    """

    metadata_backend_id = "postgresql-session-metadata-v1"
    history_backend_id = "encrypted-local-sqlite-history-v1"

    def __init__(
        self,
        settings: PostgreSQLConnectionSettings,
        history_root: str | Path,
        policy: SQLiteSessionPolicy,
        history_key: SessionHistoryKey | None = None,
        *,
        previous_history_key: SessionHistoryKey | None = None,
        key_rotation_policy: SQLiteSessionKeyRotationPolicy | None = None,
        connect_factory: ConnectFactory | None = None,
    ) -> None:
        super().__init__(
            history_root,
            policy,
            history_key,
            previous_history_key=previous_history_key,
            key_rotation_policy=key_rotation_policy,
        )
        self.settings = settings
        self.connect_factory = connect_factory

    @contextmanager
    def _connection(self) -> Iterator[PostgreSQLConnectionAdapter]:
        with postgresql_connection(self.settings, self.connect_factory) as connection:
            yield connection

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink() or not self.root.is_dir():
            raise SessionIntegrityError("Session root must be a real directory")
        self._validate_database_path(self.history_db)
        with self._connection() as connection:
            connection.executescript(_SCHEMA)
