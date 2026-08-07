from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from okcanvas_agent_runtime.adapters.persistence.postgresql.driver import (
    ConnectFactory,
    PostgreSQLConnectionAdapter,
    PostgreSQLConnectionSettings,
    postgresql_connection,
)
from okcanvas_agent_runtime.adapters.persistence.run_submission import (
    SQLiteRunSubmissionStore,
    _MIGRATION_COLUMNS,
    _SCHEMA,
    _canonical_payload,
)
from okcanvas_agent_runtime.application.submissions.errors import RunSubmissionNotFound


class PostgreSQLRunSubmissionStore(SQLiteRunSubmissionStore):
    """PostgreSQL Submission ledger and governed-admission transaction owner."""

    def __init__(
        self,
        settings: PostgreSQLConnectionSettings,
        *,
        connect_factory: ConnectFactory | None = None,
    ) -> None:
        self.settings = settings
        self._connect_factory = connect_factory

    @contextmanager
    def _connection(self) -> Iterator[PostgreSQLConnectionAdapter]:
        with postgresql_connection(self.settings, self._connect_factory) as connection:
            yield connection

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("BEGIN")
            try:
                connection.executescript(_SCHEMA)
                for name, declaration in _MIGRATION_COLUMNS.items():
                    connection.execute(
                        f"ALTER TABLE run_submission_preflight "
                        f"ADD COLUMN IF NOT EXISTS {name} {declaration}"
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _require_submission(
        connection: PostgreSQLConnectionAdapter,
        submission_id: str,
    ):
        row = connection.execute(
            "SELECT * FROM run_submission_preflight "
            "WHERE submission_id = ? FOR UPDATE",
            (submission_id,),
        ).fetchone()
        if row is None:
            raise RunSubmissionNotFound(f"Run submission preflight not found: {submission_id}")
        return row

    @staticmethod
    def _insert_event(
        connection: PostgreSQLConnectionAdapter,
        *,
        run_id: str,
        event_type: str,
        payload: dict[str, object],
        payload_schema_version: str,
        occurred_at: str,
    ) -> None:
        connection.execute("SELECT run_id FROM run WHERE run_id = ? FOR UPDATE", (run_id,))
        sequence = int(
            connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence "
                "FROM run_event WHERE run_id = ?",
                (run_id,),
            ).fetchone()["next_sequence"]
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
