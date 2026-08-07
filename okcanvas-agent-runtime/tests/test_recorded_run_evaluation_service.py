from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.bootstrap.development_cli import main
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.application.evaluation import (
    RecordedRunEvaluationError,
    RecordedRunEvaluationErrorCode,
    RecordedRunEvaluationService,
    SQLiteEvaluationStore,
)
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.domain.runs import EventSource, RunStatus, TaskStatus
from tests.artifact_test_support import artifact_service, local_blob_path, tamper_local_artifact

ROOT = Path(__file__).resolve().parents[1]


def _seed_recorded_run(
    tmp_path: Path,
    *,
    output: dict | None = None,
    definition_sha256: str | None = None,
    runtime_binding_sha256: str | None = None,
    complete: bool = True,
) -> tuple[SQLiteProductStore, str, Path, str | None]:
    database = tmp_path / "product.sqlite3"
    artifact_root = tmp_path / "artifacts"
    store = SQLiteProductStore(database)
    store.initialize()
    definition = AgentDefinitionCatalog(ROOT).resolve("reference-research-agent")
    runtime_binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    task = store.create_task(
        task_type="GENERIC_AGENT_EXECUTION",
        input_sha256="a" * 64,
        agent_definition_id=definition.agent_id,
        agent_definition_version=definition.version,
    )
    run = store.create_run(task_id=task.task_id)
    store.transition_task(task.task_id, TaskStatus.RUNNING)
    store.transition_run(
        run.run_id,
        RunStatus.RUNNING,
        event_type="run.started",
        payload={
            "agent_definition_id": definition.agent_id,
            "agent_definition_version": definition.version,
        },
        payload_schema_version="okcanvas-generic-run-started-v1",
    )
    store.append_event(
        run.run_id,
        event_type="agent.definition.resolved",
        source=EventSource.RUNTIME,
        payload={
            "agent_definition_id": definition.agent_id,
            "agent_definition_version": definition.version,
            "agent_definition_sha256": definition_sha256 or definition.definition_sha256,
            "runtime_binding_sha256": (
                runtime_binding_sha256 or runtime_binding.runtime_binding_sha256
            ),
            "output_contract": definition.output_contract,
            "local_tool_count": 0,
            "mcp_server_ids": ["reference-catalog"],
            "mcp_server_count": 1,
            "handoff_count": 0,
            "session_mode": "disabled",
        },
        payload_schema_version="okcanvas-agent-definition-resolved-v1",
    )
    store.append_event(
        run.run_id,
        event_type="model.started",
        source=EventSource.AGENT_SDK,
        payload={"agent_id": definition.agent_id, "model": "fixture-model", "input_item_count": 1},
        payload_schema_version="okcanvas-agent-sdk-lifecycle-v1",
    )
    store.append_event(
        run.run_id,
        event_type="tool.completed",
        source=EventSource.MCP,
        payload={
            "server_id": "reference-catalog",
            "tool_name": "search_reference",
            "tool_call_id_present": True,
            "result_present": True,
            "result_persisted": False,
        },
        payload_schema_version="okcanvas-agent-sdk-lifecycle-v1",
    )
    store.append_event(
        run.run_id,
        event_type="tool.completed",
        source=EventSource.MCP,
        payload={
            "server_id": "reference-catalog",
            "tool_name": "read_reference_file",
            "tool_call_id_present": True,
            "result_present": True,
            "result_persisted": False,
        },
        payload_schema_version="okcanvas-agent-sdk-lifecycle-v1",
    )
    if not complete:
        return store, run.run_id, artifact_root, None

    store.update_run_execution_metadata(
        run.run_id,
        trace_id="trace_fixture",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
    )
    artifact = artifact_service(store, artifact_root).create_json(
        run_id=run.run_id,
        artifact_type="agent.final-output",
        payload=(
            output
            or {
                "status": "PARTIAL",
                "summary": "sensitive recorded output must not enter evaluation storage",
                "findings": [],
                "unverified": [],
            }
        ),
    )
    store.append_event(
        run.run_id,
        event_type="artifact.created",
        source=EventSource.RUNTIME,
        payload={
            "artifact_id": artifact.artifact_id,
            "artifact_type": artifact.artifact_type,
            "sha256": artifact.sha256,
            "byte_length": artifact.byte_length,
            "media_type": artifact.media_type,
        },
        payload_schema_version="okcanvas-artifact-created-v1",
    )
    usage = {
        "requests": 3,
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
        "cached_input_tokens": 0,
        "reasoning_tokens": 0,
    }
    store.transition_run(
        run.run_id,
        RunStatus.SUCCEEDED,
        event_type="run.completed",
        payload={
            "artifact_id": artifact.artifact_id,
            "trace_id": "trace_fixture",
            "response_id": "resp_fixture",
            "sdk_version": "0.19.0",
            "usage": usage,
        },
        payload_schema_version="okcanvas-generic-run-completed-v1",
    )
    store.transition_task(task.task_id, TaskStatus.SUCCEEDED)
    return store, run.run_id, artifact_root, artifact.artifact_id


def _service(
    tmp_path: Path, store: SQLiteProductStore, artifact_root: Path
) -> tuple[RecordedRunEvaluationService, SQLiteEvaluationStore]:
    evaluation_store = SQLiteEvaluationStore(tmp_path / "evaluation.sqlite3")
    evaluation_store.initialize()
    return (
        RecordedRunEvaluationService(
            project_root=ROOT,
            product_store=store,
            evaluation_store=evaluation_store,
            artifact_root=artifact_root,
            runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
            artifact_service=artifact_service(store, artifact_root),
        ),
        evaluation_store,
    )


def test_completed_product_run_is_evaluated_from_events_and_verified_artifact(tmp_path: Path) -> None:
    store, run_id, artifact_root, artifact_id = _seed_recorded_run(tmp_path)
    service, evaluation_store = _service(tmp_path, store, artifact_root)

    before_events = len(store.list_events(run_id))
    outcome = service.evaluate(run_id=run_id, case_id="reference-runstate")

    assert outcome.evaluation.state == "PASSED"
    assert outcome.evaluation.subject_run_id == run_id
    assert outcome.evaluation.checks["required_tools"] is True
    assert outcome.evaluation.metrics["total_tokens"] == 150
    assert outcome.evaluation.metrics["tool_calls"] == 2
    assert outcome.artifact_id == artifact_id
    assert outcome.event_count == before_events
    assert outcome.model == "fixture-model"
    assert len(store.list_events(run_id)) == before_events
    persisted = SQLiteEvaluationStore(tmp_path / "evaluation.sqlite3").get(
        outcome.evaluation.evaluation_id
    )
    assert persisted["state"] == "PASSED"
    assert persisted["subject_agent_definition_id"] == "reference-research-agent"
    assert persisted["subject_runtime_binding_sha256"] == (
        AgentRuntimeBindingCatalog(ROOT)
        .resolve(AgentDefinitionCatalog(ROOT).resolve("reference-research-agent"))
        .runtime_binding_sha256
    )
    assert persisted["subject_model"] == "fixture-model"
    database_bytes = (tmp_path / "evaluation.sqlite3").read_bytes()
    assert b"sensitive recorded output" not in database_bytes


def test_non_terminal_run_is_rejected_without_evaluation_result(tmp_path: Path) -> None:
    store, run_id, artifact_root, _artifact_id = _seed_recorded_run(tmp_path, complete=False)
    service, evaluation_store = _service(tmp_path, store, artifact_root)
    with pytest.raises(RecordedRunEvaluationError) as caught:
        service.evaluate(run_id=run_id, case_id="reference-runstate")
    assert caught.value.code is RecordedRunEvaluationErrorCode.RUN_NOT_SUCCEEDED
    rows, total = evaluation_store.list_results()
    assert rows == []
    assert total == 0


def test_tampered_final_output_artifact_is_rejected_without_result(tmp_path: Path) -> None:
    store, run_id, artifact_root, artifact_id = _seed_recorded_run(tmp_path)
    assert artifact_id
    tamper_local_artifact(
        store, artifact_root, artifact_id, b'{"status":"PARTIAL","summary":"tampered"}'
    )
    service, evaluation_store = _service(tmp_path, store, artifact_root)
    with pytest.raises(RecordedRunEvaluationError) as caught:
        service.evaluate(run_id=run_id, case_id="reference-runstate")
    assert caught.value.code is RecordedRunEvaluationErrorCode.FINAL_OUTPUT_ARTIFACT_INVALID
    assert evaluation_store.list_results()[1] == 0


def test_invalid_output_contract_is_rejected_without_result(tmp_path: Path) -> None:
    store, run_id, artifact_root, _artifact_id = _seed_recorded_run(
        tmp_path,
        output={"status": "UNKNOWN", "summary": "invalid contract"},
    )
    service, evaluation_store = _service(tmp_path, store, artifact_root)
    with pytest.raises(RecordedRunEvaluationError) as caught:
        service.evaluate(run_id=run_id, case_id="reference-runstate")
    assert caught.value.code is RecordedRunEvaluationErrorCode.FINAL_OUTPUT_CONTRACT_INVALID
    assert evaluation_store.list_results()[1] == 0




def test_recorded_runtime_binding_sha_drift_is_rejected(tmp_path: Path) -> None:
    store, run_id, artifact_root, _artifact_id = _seed_recorded_run(
        tmp_path, runtime_binding_sha256="0" * 64
    )
    service, evaluation_store = _service(tmp_path, store, artifact_root)
    with pytest.raises(RecordedRunEvaluationError) as caught:
        service.evaluate(run_id=run_id, case_id="reference-runstate")
    assert caught.value.code is RecordedRunEvaluationErrorCode.RUNTIME_BINDING_DRIFT
    assert evaluation_store.list_results()[1] == 0


def test_recorded_runtime_binding_metadata_mismatch_is_rejected(tmp_path: Path) -> None:
    store, run_id, artifact_root, _artifact_id = _seed_recorded_run(tmp_path)
    with store._connection() as connection:
        row = connection.execute(
            "SELECT payload_json FROM run_event WHERE run_id=? AND event_type=?",
            (run_id, "agent.definition.resolved"),
        ).fetchone()
        payload = json.loads(str(row[0]))
        payload["mcp_server_count"] = 0
        connection.execute(
            "UPDATE run_event SET payload_json=? WHERE run_id=? AND event_type=?",
            (json.dumps(payload, sort_keys=True), run_id, "agent.definition.resolved"),
        )
    service, evaluation_store = _service(tmp_path, store, artifact_root)
    with pytest.raises(RecordedRunEvaluationError) as caught:
        service.evaluate(run_id=run_id, case_id="reference-runstate")
    assert caught.value.code is RecordedRunEvaluationErrorCode.RUNTIME_BINDING_DRIFT
    assert evaluation_store.list_results()[1] == 0

def test_agent_definition_sha_drift_is_rejected(tmp_path: Path) -> None:
    store, run_id, artifact_root, _artifact_id = _seed_recorded_run(
        tmp_path, definition_sha256="0" * 64
    )
    service, evaluation_store = _service(tmp_path, store, artifact_root)
    with pytest.raises(RecordedRunEvaluationError) as caught:
        service.evaluate(run_id=run_id, case_id="reference-runstate")
    assert caught.value.code is RecordedRunEvaluationErrorCode.AGENT_DEFINITION_DRIFT
    assert evaluation_store.list_results()[1] == 0


class _UnusedGateway:
    async def run(self, **_kwargs):  # pragma: no cover - recorded evaluation never invokes it
        raise AssertionError("recorded evaluation must not invoke the model gateway")


def test_control_api_creates_evaluation_for_recorded_run_without_model_call(tmp_path: Path) -> None:
    _store, run_id, artifact_root, _artifact_id = _seed_recorded_run(tmp_path)
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=artifact_root,
        evaluation_db=tmp_path / "evaluation.sqlite3",
        admin_key="recorded-evaluation-admin",
        gateway=_UnusedGateway(),
    )
    with TestClient(app) as client:
        unauthorized = client.post(
            f"/v1/runs/{run_id}/evaluations", json={"case_id": "reference-runstate"}
        )
        assert unauthorized.status_code == 401
        response = client.post(
            f"/v1/runs/{run_id}/evaluations",
            headers={"X-OKCanvas-Admin-Key": "recorded-evaluation-admin"},
            json={"case_id": "reference-runstate"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["schema_version"] == "okcanvas-control-evaluation-result-v1"
        assert body["subject_run_id"] == run_id
        assert body["state"] == "PASSED"
        assert body["checks"]["required_tools"] is True
        assert "sensitive recorded output" not in str(body)


def test_control_api_maps_non_terminal_recorded_run_to_conflict(tmp_path: Path) -> None:
    _store, run_id, artifact_root, _artifact_id = _seed_recorded_run(tmp_path, complete=False)
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=artifact_root,
        evaluation_db=tmp_path / "evaluation.sqlite3",
        admin_key="recorded-evaluation-admin",
        gateway=_UnusedGateway(),
    )
    with TestClient(app) as client:
        response = client.post(
            f"/v1/runs/{run_id}/evaluations",
            headers={"X-OKCanvas-Admin-Key": "recorded-evaluation-admin"},
            json={"case_id": "reference-runstate"},
        )
    assert response.status_code == 409
    assert response.json()["code"] == "RUN_NOT_SUCCEEDED"


def test_recorded_evaluation_cli_uses_product_state_not_envelope_files(
    tmp_path: Path, capsys
) -> None:
    _store, run_id, artifact_root, _artifact_id = _seed_recorded_run(tmp_path)
    exit_code = main(
        [
            "evaluation-run-recorded",
            "--project-root",
            str(ROOT),
            "--run-id",
            run_id,
            "--case-id",
            "reference-runstate",
            "--product-db",
            str(tmp_path / "product.sqlite3"),
            "--artifact-root",
            str(artifact_root),
            "--evaluation-db",
            str(tmp_path / "evaluation.sqlite3"),
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "okcanvas-recorded-run-evaluation-v1"
    assert payload["evaluation"]["subject_run_id"] == run_id
    assert payload["evaluation"]["state"] == "PASSED"


def test_artifact_path_outside_configured_root_is_rejected_before_content_load(
    tmp_path: Path,
) -> None:
    store, run_id, artifact_root, artifact_id = _seed_recorded_run(tmp_path)
    assert artifact_id
    artifact = store.get_artifact(artifact_id)
    outside = tmp_path / "outside-final-output.json"
    outside.write_bytes(local_blob_path(artifact_root, artifact.storage_path).read_bytes())
    with store._connection() as connection:
        connection.execute(
            "UPDATE artifact SET storage_path=? WHERE artifact_id=?",
            ("file://" + str(outside.resolve()), artifact_id),
        )
    service, evaluation_store = _service(tmp_path, store, artifact_root)
    with pytest.raises(RecordedRunEvaluationError) as caught:
        service.evaluate(run_id=run_id, case_id="reference-runstate")
    assert caught.value.code is RecordedRunEvaluationErrorCode.FINAL_OUTPUT_ARTIFACT_INVALID
    assert evaluation_store.list_results()[1] == 0
