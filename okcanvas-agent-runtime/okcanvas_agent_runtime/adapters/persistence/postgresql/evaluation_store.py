from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from okcanvas_agent_runtime.adapters.persistence.postgresql.driver import (
    ConnectFactory,
    PostgreSQLConnectionAdapter,
    PostgreSQLConnectionSettings,
    postgresql_connection,
)
from okcanvas_agent_runtime.application.evaluation.service import SQLiteEvaluationStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS evaluation_result(
  evaluation_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, case_version TEXT NOT NULL,
  case_manifest_sha256 TEXT NOT NULL, subject_run_id TEXT NOT NULL,
  subject_agent_definition_id TEXT NOT NULL,
  subject_runtime_binding_sha256 TEXT NOT NULL DEFAULT '', subject_model TEXT,
  state TEXT NOT NULL, checks_json TEXT NOT NULL, metrics_json TEXT NOT NULL,
  failures_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evaluation_case_created
  ON evaluation_result(case_id, created_at);
CREATE INDEX IF NOT EXISTS idx_evaluation_run_created
  ON evaluation_result(subject_run_id, created_at);
CREATE TABLE IF NOT EXISTS evaluation_suite_run(
  suite_run_id TEXT PRIMARY KEY, suite_id TEXT NOT NULL, suite_version TEXT NOT NULL,
  suite_manifest_sha256 TEXT NOT NULL, state TEXT NOT NULL,
  comparison_state TEXT NOT NULL, baseline_id TEXT,
  subject_count INTEGER NOT NULL, evaluation_count INTEGER NOT NULL,
  aggregate_json TEXT NOT NULL, regressions_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_suite_run_created
  ON evaluation_suite_run(suite_id, created_at);
CREATE TABLE IF NOT EXISTS evaluation_suite_member(
  suite_run_id TEXT NOT NULL, subject_id TEXT NOT NULL, slot_id TEXT NOT NULL,
  case_id TEXT NOT NULL, subject_run_id TEXT NOT NULL, evaluation_id TEXT NOT NULL,
  state TEXT NOT NULL, metrics_json TEXT NOT NULL,
  PRIMARY KEY(suite_run_id, subject_id)
);
CREATE TABLE IF NOT EXISTS evaluation_baseline(
  baseline_id TEXT PRIMARY KEY, suite_id TEXT NOT NULL, suite_version TEXT NOT NULL,
  suite_manifest_sha256 TEXT NOT NULL, source_suite_run_id TEXT NOT NULL,
  label TEXT NOT NULL, aggregate_json TEXT NOT NULL, members_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evaluation_baseline_suite
  ON evaluation_baseline(suite_id, created_at);
"""


class PostgreSQLEvaluationStore(SQLiteEvaluationStore):
    """PostgreSQL implementation retaining the deterministic Evaluation contract."""

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
            connection.execute("BEGIN")
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(_SCHEMA)
    def statistics(self) -> dict[str, object]:
        with self._connection() as db:
            evaluation_total = int(db.execute("SELECT COUNT(*) FROM evaluation_result").fetchone()[0])
            evaluation_rows = db.execute(
                "SELECT state, COUNT(*) AS count FROM evaluation_result GROUP BY state"
            ).fetchall()
            suite_run_total = int(db.execute("SELECT COUNT(*) FROM evaluation_suite_run").fetchone()[0])
            baseline_total = int(db.execute("SELECT COUNT(*) FROM evaluation_baseline").fetchone()[0])
        states = {"PASSED": 0, "FAILED": 0}
        for row in evaluation_rows:
            states[str(row["state"])] = int(row["count"])
        return {
            "evaluation_total": evaluation_total,
            "evaluation_states": states,
            "suite_run_total": suite_run_total,
            "baseline_total": baseline_total,
        }

