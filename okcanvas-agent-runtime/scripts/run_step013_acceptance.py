from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.evaluation import (
    EvaluationSuiteError,
    EvaluationSuiteService,
    EvaluationSuiteSubject,
    RecordedRunEvaluationService,
    SQLiteEvaluationStore,
)
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.domain.runs import EventSource, RunStatus, TaskStatus
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step013-acceptance-admin-key"
HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SENSITIVE_OUTPUT = "STEP013-SENSITIVE-OUTPUT-MUST-NOT-BE-IN-EVALUATION-DB"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _seed_run(
    root: Path,
    store: SQLiteProductStore,
    *,
    suffix: str,
    total_tokens: int = 150,
    include_read_tool: bool = True,
) -> tuple[str, str]:
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
        payload={"agent_id": definition.agent_id, "model": "step013-fixture-model", "input_item_count": 1},
        payload_schema_version="okcanvas-agent-sdk-lifecycle-v1",
    )
    tools = ["search_reference"] + (["read_reference_file"] if include_read_tool else [])
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
    artifact_path = root / "artifacts" / run.run_id / "final-output.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "status": "PARTIAL",
                "summary": f"{SENSITIVE_OUTPUT}:{suffix}",
                "findings": [],
                "unverified": [],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    artifact = store.register_artifact(
        run_id=run.run_id,
        artifact_type="agent.final-output",
        path=artifact_path,
        media_type="application/json",
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
    return run.run_id, artifact.artifact_id


class UnusedGateway:
    async def run(self, **_kwargs):
        raise AssertionError("STEP013 acceptance must not invoke a model")


def run_acceptance(output: Path) -> int:
    before = {item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()}
    started_at = _now()
    with AcceptanceWorkspace(step_id="STEP013", output=output) as workspace:
        root = workspace.root
        product_db = root / "product.sqlite3"
        evaluation_db = root / "evaluation.sqlite3"
        artifact_root = root / "artifacts"
        product = SQLiteProductStore(product_db)
        product.initialize()
        evaluation = SQLiteEvaluationStore(evaluation_db)
        evaluation.initialize()
        recorded = RecordedRunEvaluationService(
            project_root=ROOT,
            product_store=product,
            evaluation_store=evaluation,
            artifact_root=artifact_root,
            runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
        )
        suites = EvaluationSuiteService(
            project_root=ROOT,
            recorded_run_service=recorded,
            evaluation_store=evaluation,
        )

        base_a, _ = _seed_run(root, product, suffix="base-a")
        base_b, _ = _seed_run(root, product, suffix="base-b", total_tokens=180)
        event_counts_before = {run_id: len(product.list_events(run_id)) for run_id in (base_a, base_b)}
        suite_run = suites.run_suite(
            suite_id="reference-runstate-regression",
            subjects=(
                EvaluationSuiteSubject("primary", "runstate", base_a),
                EvaluationSuiteSubject("secondary", "runstate", base_b),
            ),
        )
        baseline = suites.create_baseline(
            source_suite_run_id=suite_run["suite_run_id"], label="Accepted STEP013 fixture"
        )
        match_a, _ = _seed_run(root, product, suffix="match-a")
        match_b, _ = _seed_run(root, product, suffix="match-b", total_tokens=180)
        matched = suites.run_suite(
            suite_id="reference-runstate-regression",
            baseline_id=baseline["baseline_id"],
            subjects=(
                EvaluationSuiteSubject("primary", "runstate", match_a),
                EvaluationSuiteSubject("secondary", "runstate", match_b),
            ),
        )
        reg_a, _ = _seed_run(root, product, suffix="reg-a")
        reg_b, _ = _seed_run(root, product, suffix="reg-b", include_read_tool=False)
        regressed = suites.run_suite(
            suite_id="reference-runstate-regression",
            baseline_id=baseline["baseline_id"],
            subjects=(
                EvaluationSuiteSubject("primary", "runstate", reg_a),
                EvaluationSuiteSubject("secondary", "runstate", reg_b),
            ),
        )

        failed_baseline_code = None
        try:
            suites.create_baseline(source_suite_run_id=regressed["suite_run_id"], label="forbidden")
        except EvaluationSuiteError as exc:
            failed_baseline_code = exc.code.value

        tampered_run, tampered_artifact_id = _seed_run(root, product, suffix="tampered")
        Path(product.get_artifact(tampered_artifact_id).storage_path).write_text(
            '{"status":"PARTIAL"}', encoding="utf-8"
        )
        total_before_tamper = evaluation.list_results()[1]
        suite_total_before_tamper = evaluation.list_suite_runs()[1]
        tamper_code = None
        try:
            suites.run_suite(
                suite_id="reference-runstate-regression",
                subjects=(EvaluationSuiteSubject("tampered", "runstate", tampered_run),),
            )
        except EvaluationSuiteError as exc:
            tamper_code = exc.code.value
        total_after_tamper = evaluation.list_results()[1]
        suite_total_after_tamper = evaluation.list_suite_runs()[1]

        shape_code = None
        try:
            suites.run_suite(
                suite_id="reference-runstate-regression",
                baseline_id=baseline["baseline_id"],
                subjects=(EvaluationSuiteSubject("different", "runstate", match_a),),
            )
        except EvaluationSuiteError as exc:
            shape_code = exc.code.value

        batch_code = None
        try:
            suites.run_suite(
                suite_id="reference-runstate-regression",
                subjects=tuple(
                    EvaluationSuiteSubject(f"subject-{index}", "runstate", base_a)
                    for index in range(5)
                ),
            )
        except EvaluationSuiteError as exc:
            batch_code = exc.code.value

        reopened = SQLiteEvaluationStore(evaluation_db)
        reopened.initialize()
        reopened_suite = reopened.get_suite_run(matched["suite_run_id"])
        reopened_baseline = reopened.get_baseline(baseline["baseline_id"])

        app = create_app(
            project_root=ROOT,
            product_db=product_db,
            artifact_root=artifact_root,
            evaluation_db=evaluation_db,
            admin_key=ADMIN_KEY,
            gateway=UnusedGateway(),
        )
        api_run, _ = _seed_run(root, product, suffix="api")
        with TestClient(app) as client:
            unauthenticated = client.get("/v1/evaluation-suites")
            catalog_response = client.get("/v1/evaluation-suites", headers=HEADERS)
            api_suite_response = client.post(
                "/v1/evaluation-suite-runs",
                headers=HEADERS,
                json={
                    "suite_id": "reference-runstate-regression",
                    "subjects": [
                        {"subject_id": "api", "slot_id": "runstate", "run_id": api_run}
                    ],
                },
            )
        event_counts_after = {run_id: len(product.list_events(run_id)) for run_id in (base_a, base_b)}
        evaluation_bytes = evaluation_db.read_bytes()

    after = {item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()}
    checks = {
        "suite_definition_loaded": suite_run["suite_id"] == "reference-runstate-regression",
        "bounded_batch_accepted": suite_run["subject_count"] == 2,
        "aggregate_persisted": suite_run["aggregate"]["total_tokens"] == 330,
        "no_implicit_baseline": suite_run["comparison_state"] == "NOT_COMPARED",
        "explicit_baseline_created": baseline["source_suite_run_id"] == suite_run["suite_run_id"],
        "matching_baseline_accepted": matched["comparison_state"] == "MATCHED",
        "regression_detected": regressed["comparison_state"] == "REGRESSED",
        "passed_to_failed_detected": any(item["metric"] == "passed_to_failed" for item in regressed["regressions"]),
        "failed_suite_not_baseline": failed_baseline_code == "BASELINE_SOURCE_NOT_PASSED",
        "tampered_run_rejected": tamper_code == "RECORDED_RUN_INVALID",
        "tamper_created_no_partial_results": total_before_tamper == total_after_tamper and suite_total_before_tamper == suite_total_after_tamper,
        "baseline_shape_mismatch_rejected": shape_code == "BASELINE_INCOMPATIBLE",
        "batch_limit_enforced": batch_code == "BATCH_LIMIT_EXCEEDED",
        "history_survives_restart": reopened_suite["comparison_state"] == "MATCHED",
        "baseline_survives_restart": reopened_baseline["baseline_id"] == baseline["baseline_id"],
        "api_auth_required": unauthenticated.status_code == 401,
        "api_catalog_available": catalog_response.status_code == 200,
        "api_suite_created": api_suite_response.status_code == 201,
        "product_events_unchanged": event_counts_before == event_counts_after,
        "raw_output_not_persisted": SENSITIVE_OUTPUT.encode("utf-8") not in evaluation_bytes,
        "references_unchanged": before == after,
    }
    payload: dict[str, object] = {
        "schema_version": "okcanvas-step013-acceptance-v1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started_at,
        "completed_at": _now(),
        "checks": checks,
        "suite_run_id": suite_run["suite_run_id"],
        "baseline_id": baseline["baseline_id"],
        "matched_suite_run_id": matched["suite_run_id"],
        "regressed_suite_run_id": regressed["suite_run_id"],
        "aggregate": suite_run["aggregate"],
        "regressions": regressed["regressions"],
    }
    payload = workspace.finalize(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP013_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
