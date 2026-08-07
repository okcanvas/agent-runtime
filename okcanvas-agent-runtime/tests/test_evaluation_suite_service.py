from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.application.evaluation import (
    EvaluationSuiteCatalog,
    EvaluationSuiteError,
    EvaluationSuiteErrorCode,
    EvaluationSuiteService,
    EvaluationSuiteSubject,
    RecordedRunEvaluationService,
    SQLiteEvaluationStore,
)
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.domain.runs import EventSource, RunStatus, TaskStatus
from tests.artifact_test_support import artifact_service, tamper_local_artifact

ROOT = Path(__file__).resolve().parents[1]


def _seed_run(
    root: Path,
    store: SQLiteProductStore,
    *,
    suffix: str,
    total_tokens: int = 150,
    include_read_tool: bool = True,
) -> str:
    definition = AgentDefinitionCatalog(ROOT).resolve("reference-research-agent")
    runtime_binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    task = store.create_task(
        task_type="GENERIC_AGENT_EXECUTION",
        input_sha256=hashlib.sha256(suffix.encode("utf-8")).hexdigest(),
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
            "agent_definition_sha256": definition.definition_sha256,
            "runtime_binding_sha256": runtime_binding.runtime_binding_sha256,
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
    tools = ["search_reference"]
    if include_read_tool:
        tools.append("read_reference_file")
    for tool_name in tools:
        store.append_event(
            run.run_id,
            event_type="tool.completed",
            source=EventSource.MCP,
            payload={
                "server_id": "reference-catalog",
                "tool_name": tool_name,
                "tool_call_id_present": True,
                "result_present": True,
                "result_persisted": False,
            },
            payload_schema_version="okcanvas-agent-sdk-lifecycle-v1",
        )
    input_tokens = total_tokens - 30
    output_tokens = 30
    store.update_run_execution_metadata(
        run.run_id,
        trace_id=f"trace_{suffix}",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )
    artifact_root = root / "artifacts"
    artifact = artifact_service(store, artifact_root).create_json(
        run_id=run.run_id,
        artifact_type="agent.final-output",
        payload={
            "status": "PARTIAL",
            "summary": f"sensitive suite output {suffix}",
            "findings": [],
            "unverified": [],
        },
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
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cached_input_tokens": 0,
        "reasoning_tokens": 0,
    }
    store.transition_run(
        run.run_id,
        RunStatus.SUCCEEDED,
        event_type="run.completed",
        payload={
            "artifact_id": artifact.artifact_id,
            "trace_id": f"trace_{suffix}",
            "response_id": f"resp_{suffix}",
            "sdk_version": "0.19.0",
            "usage": usage,
        },
        payload_schema_version="okcanvas-generic-run-completed-v1",
    )
    store.transition_task(task.task_id, TaskStatus.SUCCEEDED)
    # Suite comparison acceptance must not depend on wall-clock scheduling jitter.
    connection = sqlite3.connect(store.database_path)
    try:
        connection.execute(
            "UPDATE run SET started_at=?, completed_at=? WHERE run_id=?",
            ("2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", run.run_id),
        )
        connection.commit()
    finally:
        connection.close()
    return run.run_id


def _services(tmp_path: Path):
    product_store = SQLiteProductStore(tmp_path / "product.sqlite3")
    product_store.initialize()
    evaluation_store = SQLiteEvaluationStore(tmp_path / "evaluation.sqlite3")
    evaluation_store.initialize()
    recorded = RecordedRunEvaluationService(
        project_root=ROOT,
        product_store=product_store,
        evaluation_store=evaluation_store,
        artifact_root=tmp_path / "artifacts",
        runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
            artifact_service=artifact_service(product_store, tmp_path / "artifacts"),
    )
    suite = EvaluationSuiteService(
        project_root=ROOT,
        recorded_run_service=recorded,
        evaluation_store=evaluation_store,
    )
    return product_store, evaluation_store, suite


def test_suite_catalog_is_versioned_and_bounded() -> None:
    suite = EvaluationSuiteCatalog(ROOT).resolve("reference-runstate-regression")
    assert suite.version == "1.0.0"
    assert suite.max_subjects == 4
    assert suite.slots[0].case_id == "reference-runstate"
    assert len(suite.manifest_sha256) == 64
    with pytest.raises(ValueError):
        EvaluationSuiteCatalog(ROOT).resolve("../outside")


def test_suite_run_persists_evaluations_and_aggregate_atomically(tmp_path: Path) -> None:
    product, evaluation, service = _services(tmp_path)
    first = _seed_run(tmp_path, product, suffix="a")
    second = _seed_run(tmp_path, product, suffix="b", total_tokens=180)

    result = service.run_suite(
        suite_id="reference-runstate-regression",
        subjects=(
            EvaluationSuiteSubject("primary", "runstate", first),
            EvaluationSuiteSubject("secondary", "runstate", second),
        ),
    )

    assert result["state"] == "PASSED"
    assert result["comparison_state"] == "NOT_COMPARED"
    assert result["aggregate"]["evaluation_count"] == 2
    assert result["aggregate"]["total_tokens"] == 330
    assert len(result["members"]) == 2
    rows, total = evaluation.list_results()
    assert total == 2
    assert {row["subject_run_id"] for row in rows} == {first, second}
    reopened = SQLiteEvaluationStore(tmp_path / "evaluation.sqlite3")
    assert reopened.get_suite_run(result["suite_run_id"])["aggregate"] == result["aggregate"]
    database = (tmp_path / "evaluation.sqlite3").read_bytes()
    assert b"sensitive suite output" not in database


def test_failed_preparation_creates_no_partial_evaluation_or_suite_result(tmp_path: Path) -> None:
    product, evaluation, service = _services(tmp_path)
    good = _seed_run(tmp_path, product, suffix="c")
    bad = _seed_run(tmp_path, product, suffix="d")
    artifact_event = next(event for event in product.list_events(bad) if event.event_type == "artifact.created")
    tamper_local_artifact(
        product, tmp_path / "artifacts", artifact_event.payload["artifact_id"], b'{"status":"PARTIAL"}'
    )

    with pytest.raises(EvaluationSuiteError) as caught:
        service.run_suite(
            suite_id="reference-runstate-regression",
            subjects=(
                EvaluationSuiteSubject("good", "runstate", good),
                EvaluationSuiteSubject("bad", "runstate", bad),
            ),
        )
    assert caught.value.code is EvaluationSuiteErrorCode.RECORDED_RUN_INVALID
    assert evaluation.list_results()[1] == 0
    assert evaluation.list_suite_runs()[1] == 0


def test_explicit_baseline_detects_passed_to_failed_regression(tmp_path: Path) -> None:
    product, evaluation, service = _services(tmp_path)
    baseline_first = _seed_run(tmp_path, product, suffix="e")
    baseline_second = _seed_run(tmp_path, product, suffix="f")
    baseline_run = service.run_suite(
        suite_id="reference-runstate-regression",
        subjects=(
            EvaluationSuiteSubject("primary", "runstate", baseline_first),
            EvaluationSuiteSubject("secondary", "runstate", baseline_second),
        ),
    )
    baseline = service.create_baseline(
        source_suite_run_id=baseline_run["suite_run_id"], label="Approved fixture baseline"
    )
    current_first = _seed_run(tmp_path, product, suffix="g")
    current_second = _seed_run(tmp_path, product, suffix="h", include_read_tool=False)
    current = service.run_suite(
        suite_id="reference-runstate-regression",
        baseline_id=baseline["baseline_id"],
        subjects=(
            EvaluationSuiteSubject("primary", "runstate", current_first),
            EvaluationSuiteSubject("secondary", "runstate", current_second),
        ),
    )
    assert current["state"] == "FAILED"
    assert current["comparison_state"] == "REGRESSED"
    assert current["regressions"][0]["metric"] == "passed_to_failed"
    assert evaluation.get_baseline(baseline["baseline_id"])["source_suite_run_id"] == baseline_run["suite_run_id"]


def test_baseline_shape_and_batch_limits_are_fail_closed(tmp_path: Path) -> None:
    product, evaluation, service = _services(tmp_path)
    run_ids = [_seed_run(tmp_path, product, suffix=character) for character in "ijklm"]
    with pytest.raises(EvaluationSuiteError) as batch:
        service.run_suite(
            suite_id="reference-runstate-regression",
            subjects=tuple(
                EvaluationSuiteSubject(f"subject-{index}", "runstate", run_id)
                for index, run_id in enumerate(run_ids)
            ),
        )
    assert batch.value.code is EvaluationSuiteErrorCode.BATCH_LIMIT_EXCEEDED
    assert evaluation.list_results()[1] == 0

    baseline_run = service.run_suite(
        suite_id="reference-runstate-regression",
        subjects=(EvaluationSuiteSubject("primary", "runstate", run_ids[0]),),
    )
    baseline = service.create_baseline(
        source_suite_run_id=baseline_run["suite_run_id"], label="Shape baseline"
    )
    with pytest.raises(EvaluationSuiteError) as shape:
        service.run_suite(
            suite_id="reference-runstate-regression",
            baseline_id=baseline["baseline_id"],
            subjects=(EvaluationSuiteSubject("different", "runstate", run_ids[1]),),
        )
    assert shape.value.code is EvaluationSuiteErrorCode.BASELINE_INCOMPATIBLE
    assert evaluation.list_suite_runs()[1] == 1
    assert evaluation.list_results()[1] == 1


def test_failed_suite_cannot_be_promoted_to_baseline(tmp_path: Path) -> None:
    product, _evaluation, service = _services(tmp_path)
    failed_run = _seed_run(tmp_path, product, suffix="n", include_read_tool=False)
    suite_run = service.run_suite(
        suite_id="reference-runstate-regression",
        subjects=(EvaluationSuiteSubject("primary", "runstate", failed_run),),
    )
    assert suite_run["state"] == "FAILED"
    with pytest.raises(EvaluationSuiteError) as caught:
        service.create_baseline(source_suite_run_id=suite_run["suite_run_id"], label="Bad")
    assert caught.value.code is EvaluationSuiteErrorCode.BASELINE_SOURCE_NOT_PASSED
