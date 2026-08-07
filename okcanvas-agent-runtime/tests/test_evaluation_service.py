from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.application.evaluation import EvaluationCatalog, SQLiteEvaluationStore, DeterministicEvaluator, compare_results

ROOT = Path(__file__).resolve().parents[1]


def envelope(status="PARTIAL", tokens=2785):
    return {
        "state":"SUCCEEDED", "run_id":"run_1", "agent_definition_id":"reference-research-agent", "model":"test-model",
        "result":{"status":status,"summary":"RunState summary","findings":[],"unverified":[]},
        "usage":{"requests":3,"total_tokens":tokens},
    }


def events(*tools):
    return [{"event_type":"tool.completed","payload":{"tool_name":name}} for name in tools]


def test_pass_and_persist_restart(tmp_path):
    case=EvaluationCatalog(ROOT).resolve("reference-runstate")
    result=DeterministicEvaluator().evaluate(case=case,envelope=envelope(),events=events("search_reference","read_reference_file"),duration_ms=32000)
    assert result.state == "PASSED"
    db=tmp_path/'eval.sqlite3'; store=SQLiteEvaluationStore(db); store.initialize(); store.save(case=case,envelope=envelope(),result=result)
    reopened=SQLiteEvaluationStore(db); reopened.initialize(); rows=reopened.list_case(case.case_id)
    assert len(rows)==1 and rows[0]["state"]=="PASSED"
    assert "RunState summary" not in db.read_bytes().decode("latin1")


def test_missing_required_tool_fails():
    case=EvaluationCatalog(ROOT).resolve("reference-runstate")
    result=DeterministicEvaluator().evaluate(case=case,envelope=envelope(),events=events("search_reference"),duration_ms=1)
    assert result.state == "FAILED" and "required_tools" in result.failures


def test_forbidden_tool_fails():
    case=EvaluationCatalog(ROOT).resolve("reference-runstate")
    result=DeterministicEvaluator().evaluate(case=case,envelope=envelope(),events=events("search_reference","read_reference_file","web_search"),duration_ms=1)
    assert result.state == "FAILED" and "forbidden_tools_absent" in result.failures


def test_wrong_output_and_budget_fail():
    case=EvaluationCatalog(ROOT).resolve("reference-runstate")
    result=DeterministicEvaluator().evaluate(case=case,envelope=envelope("FAILED",6000),events=events("search_reference","read_reference_file"),duration_ms=70000)
    assert {"required_result","forbidden_result_absent","token_budget","latency_budget"}.issubset(result.failures)


def test_comparison():
    left={"evaluation_id":"a","state":"PASSED","metrics":{"total_tokens":100,"duration_ms":10,"tool_calls":2}}
    right={"evaluation_id":"b","state":"FAILED","metrics":{"total_tokens":130,"duration_ms":8,"tool_calls":3}}
    result=compare_results(left,right)
    assert result["state_changed"] is True and result["token_delta"]==30 and result["duration_delta_ms"]==-2


def test_sqlite_evaluation_store_closes_every_operation_connection(tmp_path, monkeypatch):
    import okcanvas_agent_runtime.application.evaluation.service as service_module

    real_connect = service_module.sqlite3.connect
    tracked = []

    class TrackingConnection:
        def __init__(self, connection):
            object.__setattr__(self, "_connection", connection)
            object.__setattr__(self, "closed", False)

        def __getattr__(self, name):
            return getattr(self._connection, name)

        def __setattr__(self, name, value):
            if name in {"_connection", "closed"}:
                object.__setattr__(self, name, value)
            else:
                setattr(self._connection, name, value)

        def close(self):
            object.__setattr__(self, "closed", True)
            return self._connection.close()

    def tracking_connect(*args, **kwargs):
        wrapped = TrackingConnection(real_connect(*args, **kwargs))
        tracked.append(wrapped)
        return wrapped

    monkeypatch.setattr(service_module.sqlite3, "connect", tracking_connect)

    case = EvaluationCatalog(ROOT).resolve("reference-runstate")
    result = DeterministicEvaluator().evaluate(
        case=case,
        envelope=envelope(),
        events=events("search_reference", "read_reference_file"),
        duration_ms=100,
    )
    store = SQLiteEvaluationStore(tmp_path / "evaluation.sqlite3")
    store.initialize()
    store.save(case=case, envelope=envelope(), result=result)
    assert store.get(result.evaluation_id)["state"] == "PASSED"
    rows, total = store.list_results(subject_run_id="run_1")
    assert total == 1 and rows[0]["evaluation_id"] == result.evaluation_id
    assert len(tracked) == 4
    assert all(connection.closed for connection in tracked)


def test_existing_evaluation_database_adds_runtime_binding_column(tmp_path):
    import sqlite3

    database = tmp_path / "legacy-evaluation.sqlite3"
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            """CREATE TABLE evaluation_result(
              evaluation_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, case_version TEXT NOT NULL,
              case_manifest_sha256 TEXT NOT NULL, subject_run_id TEXT NOT NULL,
              subject_agent_definition_id TEXT NOT NULL, subject_model TEXT,
              state TEXT NOT NULL, checks_json TEXT NOT NULL, metrics_json TEXT NOT NULL,
              failures_json TEXT NOT NULL, created_at TEXT NOT NULL
            )"""
        )
        connection.commit()
    finally:
        connection.close()

    store = SQLiteEvaluationStore(database)
    store.initialize()
    connection = sqlite3.connect(database)
    try:
        columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(evaluation_result)")
        }
    finally:
        connection.close()
    assert "subject_runtime_binding_sha256" in columns
