from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from okcanvas_agent_runtime.adapters.persistence.product.sqlite_store import (
    SQLiteProductStore,
    _SCHEMA_V1,
    _canonical_payload,
    _utc_now,
)
from okcanvas_agent_runtime.adapters.persistence.postgresql.driver import (
    ConnectFactory,
    PostgreSQLConnectionAdapter,
    PostgreSQLConnectionSettings,
    postgresql_connection,
)
from okcanvas_agent_runtime.domain.runs.models import EventSource, RunEventRecord


class PostgreSQLProductStore(SQLiteProductStore):
    """PostgreSQL ProductStore preserving the accepted SQLite domain semantics."""

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
                connection.executescript(_SCHEMA_V1)
                connection.execute(
                    """
                    INSERT INTO schema_migration(version, applied_at)
                    VALUES(1, ?)
                    ON CONFLICT(version) DO NOTHING
                    """,
                    (_utc_now(),),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def _insert_event(
        self,
        connection: PostgreSQLConnectionAdapter,
        *,
        run_id: str,
        event_type: str,
        source: EventSource,
        payload: dict[str, Any] | None,
        payload_schema_version: str,
    ) -> RunEventRecord:
        connection.execute("SELECT run_id FROM run WHERE run_id = ? FOR UPDATE", (run_id,))
        sequence = int(
            connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence "
                "FROM run_event WHERE run_id = ?",
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
            payload=__import__("json").loads(payload_json),
        )
