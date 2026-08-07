from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from okcanvas_agent_runtime.application.evaluation.models import EvaluationCase, EvaluationResult

_ALLOWED_KEYS = {
    "schema_version", "case_id", "version", "agent_definition_id",
    "required_result", "forbidden_result", "required_tools", "forbidden_tools",
    "max_total_tokens", "max_duration_ms",
}
_VALID_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-_")


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _contains(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and _contains(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and all(any(_contains(item, wanted) for item in actual) for wanted in expected)
    return actual == expected


def _valid_identifier(value: str) -> bool:
    return bool(value) and all(character in _VALID_ID_CHARS for character in value)


class EvaluationCatalog:
    def __init__(self, project_root: str | Path) -> None:
        self.root = Path(project_root).resolve()
        self.spec_root = self.root / "specs" / "evaluations"

    def list_cases(self) -> tuple[EvaluationCase, ...]:
        if not self.spec_root.is_dir():
            return ()
        cases: list[EvaluationCase] = []
        for entry in sorted(self.spec_root.iterdir(), key=lambda item: item.name):
            if entry.is_symlink():
                raise ValueError(f"symbolic evaluation case directories are forbidden: {entry.name}")
            if not entry.is_dir():
                continue
            if not _valid_identifier(entry.name):
                raise ValueError(f"invalid evaluation case directory: {entry.name}")
            cases.append(self.resolve(entry.name))
        return tuple(cases)

    def resolve(self, case_id: str) -> EvaluationCase:
        if not _valid_identifier(case_id):
            raise ValueError("invalid case_id")
        case_directory = self.spec_root / case_id
        if case_directory.is_symlink():
            raise ValueError("symbolic evaluation case directories are forbidden")
        path = case_directory / "case.json"
        if path.is_symlink():
            raise ValueError("symbolic evaluation case files are forbidden")
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"evaluation case not found: {case_id}") from exc
        if self.spec_root.resolve() not in resolved.parents:
            raise ValueError("evaluation path escapes spec root")
        raw = resolved.read_bytes()
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("evaluation case must be an object")
        unknown = set(data) - _ALLOWED_KEYS
        missing = {"schema_version", "case_id", "version", "agent_definition_id"} - set(data)
        if unknown or missing:
            raise ValueError(
                f"evaluation case fields mismatch: missing={sorted(missing)}, unknown={sorted(unknown)}"
            )
        if data.get("schema_version") != "okcanvas-evaluation-case-v1" or data.get("case_id") != case_id:
            raise ValueError("invalid evaluation case contract")
        required_tools = tuple(data.get("required_tools") or [])
        forbidden_tools = tuple(data.get("forbidden_tools") or [])
        if any(not isinstance(item, str) or not item for item in required_tools + forbidden_tools):
            raise ValueError("evaluation tool names must be non-empty strings")
        return EvaluationCase(
            case_id=case_id,
            version=str(data["version"]),
            agent_definition_id=str(data["agent_definition_id"]),
            required_result=dict(data.get("required_result") or {}),
            forbidden_result=dict(data.get("forbidden_result") or {}),
            required_tools=required_tools,
            forbidden_tools=forbidden_tools,
            max_total_tokens=data.get("max_total_tokens"),
            max_duration_ms=data.get("max_duration_ms"),
            manifest_sha256=hashlib.sha256(raw).hexdigest(),
        )


class SQLiteEvaluationStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Open one operation-scoped connection and always release its file handle."""
        db = sqlite3.connect(self.path)
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            db.executescript("""
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
            """)
            columns = {
                str(row[1]) for row in db.execute("PRAGMA table_info(evaluation_result)").fetchall()
            }
            if "subject_runtime_binding_sha256" not in columns:
                db.execute(
                    "ALTER TABLE evaluation_result ADD COLUMN "
                    "subject_runtime_binding_sha256 TEXT NOT NULL DEFAULT ''"
                )

    @staticmethod
    def _insert_result(
        db: sqlite3.Connection,
        *,
        case: EvaluationCase,
        envelope: dict[str, Any],
        result: EvaluationResult,
    ) -> None:
        db.execute(
            """INSERT INTO evaluation_result(
              evaluation_id, case_id, case_version, case_manifest_sha256, subject_run_id,
              subject_agent_definition_id, subject_runtime_binding_sha256, subject_model,
              state, checks_json, metrics_json, failures_json, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                result.evaluation_id, result.case_id, result.case_version, case.manifest_sha256,
                result.subject_run_id, envelope.get("agent_definition_id", ""),
                envelope.get("runtime_binding_sha256", ""), envelope.get("model"),
                result.state, _canonical(result.checks), _canonical(result.metrics),
                _canonical(list(result.failures)), result.created_at,
            ),
        )

    def save(self, *, case: EvaluationCase, envelope: dict[str, Any], result: EvaluationResult) -> None:
        with self._connection() as db:
            self._insert_result(db, case=case, envelope=envelope, result=result)


    def save_suite_bundle(
        self,
        *,
        evaluations: list[tuple[EvaluationCase, dict[str, Any], EvaluationResult]],
        suite_run: dict[str, Any],
        members: list[dict[str, Any]],
    ) -> None:
        with self._connection() as db:
            for case, envelope, result in evaluations:
                self._insert_result(db, case=case, envelope=envelope, result=result)
            db.execute(
                """INSERT INTO evaluation_suite_run VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    suite_run["suite_run_id"], suite_run["suite_id"], suite_run["suite_version"],
                    suite_run["suite_manifest_sha256"], suite_run["state"],
                    suite_run["comparison_state"], suite_run.get("baseline_id"),
                    suite_run["subject_count"], suite_run["evaluation_count"],
                    _canonical(suite_run["aggregate"]), _canonical(suite_run["regressions"]),
                    suite_run["created_at"],
                ),
            )
            for member in members:
                db.execute(
                    """INSERT INTO evaluation_suite_member VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        suite_run["suite_run_id"], member["subject_id"], member["slot_id"],
                        member["case_id"], member["subject_run_id"], member["evaluation_id"],
                        member["state"], _canonical(member["metrics"]),
                    ),
                )

    def statistics(self) -> dict[str, object]:
        with self._connection() as db:
            evaluation_total = int(db.execute("SELECT COUNT(*) FROM evaluation_result").fetchone()[0])
            evaluation_rows = db.execute(
                "SELECT state, COUNT(*) FROM evaluation_result GROUP BY state"
            ).fetchall()
            suite_run_total = int(db.execute("SELECT COUNT(*) FROM evaluation_suite_run").fetchone()[0])
            baseline_total = int(db.execute("SELECT COUNT(*) FROM evaluation_baseline").fetchone()[0])
        states = {"PASSED": 0, "FAILED": 0}
        for state, count in evaluation_rows:
            states[str(state)] = int(count)
        return {
            "evaluation_total": evaluation_total,
            "evaluation_states": states,
            "suite_run_total": suite_run_total,
            "baseline_total": baseline_total,
        }

    def get_suite_run(self, suite_run_id: str) -> dict[str, Any]:
        with self._connection() as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT * FROM evaluation_suite_run WHERE suite_run_id=?", (suite_run_id,)
            ).fetchone()
            members = db.execute(
                "SELECT * FROM evaluation_suite_member WHERE suite_run_id=? ORDER BY subject_id",
                (suite_run_id,),
            ).fetchall()
        if row is None:
            raise KeyError(suite_run_id)
        result = dict(row)
        result["aggregate"] = json.loads(result.pop("aggregate_json"))
        result["regressions"] = json.loads(result.pop("regressions_json"))
        decoded_members: list[dict[str, Any]] = []
        for member in members:
            item = dict(member)
            item["metrics"] = json.loads(item.pop("metrics_json"))
            decoded_members.append(item)
        result["members"] = decoded_members
        return result

    def list_suite_runs(
        self, *, suite_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be 1..200")
        if offset < 0:
            raise ValueError("offset must be non-negative")
        where = " WHERE suite_id=?" if suite_id else ""
        params: tuple[Any, ...] = (suite_id,) if suite_id else ()
        with self._connection() as db:
            total = int(db.execute(
                f"SELECT COUNT(*) FROM evaluation_suite_run{where}", params
            ).fetchone()[0])
            rows = db.execute(
                f"SELECT suite_run_id FROM evaluation_suite_run{where} "
                "ORDER BY created_at DESC, suite_run_id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [self.get_suite_run(str(row[0])) for row in rows], total

    def create_baseline(self, baseline: dict[str, Any]) -> None:
        with self._connection() as db:
            db.execute(
                """INSERT INTO evaluation_baseline VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    baseline["baseline_id"], baseline["suite_id"], baseline["suite_version"],
                    baseline["suite_manifest_sha256"], baseline["source_suite_run_id"],
                    baseline["label"], _canonical(baseline["aggregate"]),
                    _canonical(baseline["members"]), baseline["created_at"],
                ),
            )

    def get_baseline(self, baseline_id: str) -> dict[str, Any]:
        with self._connection() as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT * FROM evaluation_baseline WHERE baseline_id=?", (baseline_id,)
            ).fetchone()
        if row is None:
            raise KeyError(baseline_id)
        result = dict(row)
        result["aggregate"] = json.loads(result.pop("aggregate_json"))
        result["members"] = json.loads(result.pop("members_json"))
        return result

    def list_baselines(
        self, *, suite_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be 1..200")
        if offset < 0:
            raise ValueError("offset must be non-negative")
        where = " WHERE suite_id=?" if suite_id else ""
        params: tuple[Any, ...] = (suite_id,) if suite_id else ()
        with self._connection() as db:
            db.row_factory = sqlite3.Row
            total = int(db.execute(
                f"SELECT COUNT(*) FROM evaluation_baseline{where}", params
            ).fetchone()[0])
            rows = db.execute(
                f"SELECT * FROM evaluation_baseline{where} "
                "ORDER BY created_at DESC, baseline_id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["aggregate"] = json.loads(item.pop("aggregate_json"))
            item["members"] = json.loads(item.pop("members_json"))
            results.append(item)
        return results, total

    @staticmethod
    def _decode_row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["checks"] = json.loads(result.pop("checks_json"))
        result["metrics"] = json.loads(result.pop("metrics_json"))
        result["failures"] = json.loads(result.pop("failures_json"))
        return result

    def get(self, evaluation_id: str) -> dict[str, Any]:
        with self._connection() as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT * FROM evaluation_result WHERE evaluation_id=?", (evaluation_id,)
            ).fetchone()
        if row is None:
            raise KeyError(evaluation_id)
        return self._decode_row(row)

    def list_results(
        self,
        *,
        case_id: str | None = None,
        subject_run_id: str | None = None,
        state: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be 1..200")
        if offset < 0:
            raise ValueError("offset must be non-negative")
        clauses: list[str] = []
        parameters: list[Any] = []
        for column, value in (
            ("case_id", case_id),
            ("subject_run_id", subject_run_id),
            ("state", state),
        ):
            if value is not None:
                clauses.append(f"{column}=?")
                parameters.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connection() as db:
            db.row_factory = sqlite3.Row
            total = int(db.execute(
                f"SELECT COUNT(*) FROM evaluation_result{where}", tuple(parameters)
            ).fetchone()[0])
            rows = db.execute(
                f"SELECT * FROM evaluation_result{where} ORDER BY created_at DESC, evaluation_id DESC LIMIT ? OFFSET ?",
                (*parameters, limit, offset),
            ).fetchall()
        return [self._decode_row(row) for row in rows], total

    def list_case(self, case_id: str) -> list[dict[str, Any]]:
        rows, _total = self.list_results(case_id=case_id, limit=200)
        return list(reversed(rows))


class DeterministicEvaluator:
    def evaluate(self, *, case: EvaluationCase, envelope: dict[str, Any], events: list[dict[str, Any]], duration_ms: int) -> EvaluationResult:
        result_data = envelope.get("result") or {}
        tool_names = [
            str((event.get("payload") or {}).get("tool_name"))
            for event in events if event.get("event_type") == "tool.completed"
        ]
        checks = {
            "agent_definition_matches": envelope.get("agent_definition_id") == case.agent_definition_id,
            "execution_succeeded": envelope.get("state") == "SUCCEEDED",
            "required_result": _contains(result_data, case.required_result),
            "forbidden_result_absent": not case.forbidden_result or not _contains(result_data, case.forbidden_result),
            "required_tools": all(name in tool_names for name in case.required_tools),
            "forbidden_tools_absent": all(name not in tool_names for name in case.forbidden_tools),
        }
        usage = envelope.get("usage") or {}
        total_tokens = int(usage.get("total_tokens") or 0)
        if case.max_total_tokens is not None:
            checks["token_budget"] = total_tokens <= case.max_total_tokens
        if case.max_duration_ms is not None:
            checks["latency_budget"] = duration_ms <= case.max_duration_ms
        failures = tuple(name for name, passed in checks.items() if not passed)
        return EvaluationResult(
            evaluation_id=f"eval_{uuid.uuid4().hex}", case_id=case.case_id,
            case_version=case.version, subject_run_id=str(envelope.get("run_id") or ""),
            state="PASSED" if not failures else "FAILED", checks=checks,
            metrics={"duration_ms": duration_ms, "total_tokens": total_tokens, "tool_calls": len(tool_names), "requests": int(usage.get("requests") or 0)},
            failures=failures, created_at=_now(),
        )


def compare_results(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    lm, rm = left["metrics"], right["metrics"]
    return {
        "schema_version": "okcanvas-evaluation-comparison-v1",
        "left_evaluation_id": left["evaluation_id"], "right_evaluation_id": right["evaluation_id"],
        "state_changed": left["state"] != right["state"],
        "token_delta": int(rm["total_tokens"]) - int(lm["total_tokens"]),
        "duration_delta_ms": int(rm["duration_ms"]) - int(lm["duration_ms"]),
        "tool_call_delta": int(rm["tool_calls"]) - int(lm["tool_calls"]),
    }
