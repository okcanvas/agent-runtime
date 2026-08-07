from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from okcanvas_agent_runtime.adapters.persistence.postgresql.driver import (
    ConnectFactory,
    PostgreSQLConnectionAdapter,
    PostgreSQLConnectionSettings,
    postgresql_connection,
)
from okcanvas_agent_runtime.adapters.persistence.tool_approval import SQLiteToolApprovalStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS governed_tool_approval (
  approval_id TEXT PRIMARY KEY,
  submission_id TEXT NOT NULL UNIQUE,
  task_id TEXT NOT NULL UNIQUE,
  run_id TEXT NOT NULL UNIQUE,
  session_id TEXT,
  session_item_count_before INTEGER,
  state TEXT NOT NULL,
  decision TEXT,
  tool_name TEXT NOT NULL,
  tool_call_id_sha256 TEXT NOT NULL,
  arguments_sha256 TEXT NOT NULL,
  run_state_ref TEXT NOT NULL UNIQUE,
  run_state_sha256 TEXT NOT NULL,
  run_state_byte_length INTEGER NOT NULL,
  run_state_key_id TEXT NOT NULL,
  trace_id TEXT,
  response_id TEXT,
  tool_execution_count INTEGER NOT NULL DEFAULT 0,
  resume_generation INTEGER NOT NULL DEFAULT 0,
  resume_token_sha256 TEXT,
  created_at TEXT NOT NULL,
  decided_at TEXT,
  completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_governed_tool_approval_state
ON governed_tool_approval(state, created_at);
"""


class PostgreSQLToolApprovalStore(SQLiteToolApprovalStore):
    """PostgreSQL Tool Approval store sharing the Product transaction domain.

    The inherited state machine is intentionally retained. Only connection and
    schema ownership change, so approval interruption/resume updates remain in
    one PostgreSQL transaction with Task, Run, Submission and Run Event rows.
    """

    def __init__(
        self,
        settings: PostgreSQLConnectionSettings,
        *,
        connect_factory: ConnectFactory | None = None,
    ) -> None:
        self.settings = settings
        self.connect_factory = connect_factory

    @contextmanager
    def _connection(self) -> Iterator[PostgreSQLConnectionAdapter]:
        with postgresql_connection(self.settings, self.connect_factory) as connection:
            yield connection

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(_SCHEMA)
