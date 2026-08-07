from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.evaluation import (
    RecordedRunEvaluationError,
    RecordedRunEvaluationErrorCode,
    RecordedRunEvaluationService,
    SQLiteEvaluationStore,
)
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.domain.runs import EventSource, RunStatus, TaskStatus
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step012-local-admin-key"
HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SENSITIVE_OUTPUT = "STEP012 sensitive recorded output must not enter evaluation storage"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _seed_completed_run(root: Path) -> tuple[SQLiteProductStore, str, Path, str]:
    product_db = root / "product.sqlite3"
    artifact_root = root / "artifacts"
    store = SQLiteProductStore(product_db)
    store.initialize()
    definition = AgentDefinitionCatalog(ROOT).resolve("reference-research-agent")
    runtime_binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    task = store.create_task(
        task_type="GENERIC_AGENT_EXECUTION",
        input_sha256="1" * 64,
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
        payload={"agent_id": definition.agent_id, "model": "acceptance-model", "input_item_count": 1},
        payload_schema_version="okcanvas-agent-sdk-lifecycle-v1",
    )
    for tool_name in ("search_reference", "read_reference_file"):
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
    store.update_run_execution_metadata(
        run.run_id,
        trace_id="trace_step012",
        input_tokens=120,
        output_tokens=30,
        total_tokens=150,
    )
    artifact_path = artifact_root / run.run_id / "final-output.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "status": "PARTIAL",
                "summary": SENSITIVE_OUTPUT,
                "findings": [],
                "unverified": [],
            },
            ensure_ascii=False,
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
        "input_tokens": 120,
        "output_tokens": 30,
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
            "trace_id": "trace_step012",
            "response_id": "resp_step012",
            "sdk_version": "0.19.0",
            "usage": usage,
        },
        payload_schema_version="okcanvas-generic-run-completed-v1",
    )
    store.transition_task(task.task_id, TaskStatus.SUCCEEDED)
    return store, run.run_id, artifact_root, artifact.artifact_id


def _seed_running_run(store: SQLiteProductStore) -> str:
    definition = AgentDefinitionCatalog(ROOT).resolve("reference-research-agent")
    runtime_binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    task = store.create_task(
        task_type="GENERIC_AGENT_EXECUTION",
        input_sha256="2" * 64,
        agent_definition_id=definition.agent_id,
        agent_definition_version=definition.version,
    )
    run = store.create_run(task_id=task.task_id)
    return run.run_id


class UnusedGateway:
    async def run(self, **_kwargs):
        raise AssertionError("STEP012 recorded evaluation must not invoke the model gateway")


def run_acceptance(output: Path) -> int:
    before = {
        item.reference_id: item.to_dict()
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    started_at = _now()
    with AcceptanceWorkspace(step_id="STEP012", output=output) as workspace:
        root = workspace.root
        store, run_id, artifact_root, artifact_id = _seed_completed_run(root)
        running_run_id = _seed_running_run(store)
        evaluation_db = root / "evaluation.sqlite3"
        evaluation_store = SQLiteEvaluationStore(evaluation_db)
        evaluation_store.initialize()
        service = RecordedRunEvaluationService(
            project_root=ROOT,
            product_store=store,
            evaluation_store=evaluation_store,
            artifact_root=artifact_root,
            runtime_bindings=AgentRuntimeBindingCatalog(ROOT),
        )
        event_count_before = len(store.list_events(run_id))
        direct = service.evaluate(run_id=run_id, case_id="reference-runstate")
        event_count_after = len(store.list_events(run_id))
        history_after_restart, history_total = SQLiteEvaluationStore(
            evaluation_db
        ).list_results(subject_run_id=run_id)
        non_terminal_code = None
        try:
            service.evaluate(run_id=running_run_id, case_id="reference-runstate")
        except RecordedRunEvaluationError as exc:
            non_terminal_code = exc.code.value

        app = create_app(
            project_root=ROOT,
            product_db=root / "product.sqlite3",
            artifact_root=artifact_root,
            evaluation_db=evaluation_db,
            admin_key=ADMIN_KEY,
            gateway=UnusedGateway(),
        )
        with TestClient(app) as client:
            unauthorized = client.post(
                f"/v1/runs/{run_id}/evaluations",
                json={"case_id": "reference-runstate"},
            )
            api_response = client.post(
                f"/v1/runs/{run_id}/evaluations",
                headers=HEADERS,
                json={"case_id": "reference-runstate"},
            )
        artifact_path = Path(store.get_artifact(artifact_id).storage_path)
        artifact_path.write_text(
            '{"status":"PARTIAL","summary":"tampered"}', encoding="utf-8"
        )
        tamper_code = None
        try:
            service.evaluate(run_id=run_id, case_id="reference-runstate")
        except RecordedRunEvaluationError as exc:
            tamper_code = exc.code.value
        final_rows, final_total = SQLiteEvaluationStore(evaluation_db).list_results(
            subject_run_id=run_id
        )
        evaluation_bytes = evaluation_db.read_bytes()

    after = {
        item.reference_id: item.to_dict()
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    api_body = api_response.json()
    checks = {
        "recorded_run_loaded": direct.evaluation.subject_run_id == run_id,
        "canonical_events_loaded": direct.event_count == event_count_before,
        "artifact_verified": direct.artifact_id == artifact_id
        and len(direct.artifact_sha256) == 64,
        "output_contract_validated": direct.evaluation.state == "PASSED",
        "definition_identity_verified": direct.model == "acceptance-model",
        "usage_reconstructed": direct.evaluation.metrics["total_tokens"] == 150,
        "tool_calls_reconstructed": direct.evaluation.metrics["tool_calls"] == 2,
        "history_survives_restart": history_total == 1
        and history_after_restart[0]["evaluation_id"] == direct.evaluation.evaluation_id,
        "product_event_journal_unchanged": event_count_before == event_count_after,
        "non_terminal_run_rejected": non_terminal_code == "RUN_NOT_SUCCEEDED",
        "api_auth_required": unauthorized.status_code == 401,
        "api_evaluation_created": api_response.status_code == 201
        and api_body["subject_run_id"] == run_id
        and api_body["state"] == "PASSED",
        "tampered_artifact_rejected": tamper_code == "FINAL_OUTPUT_ARTIFACT_INVALID",
        "tamper_created_no_result": final_total == 2 and len(final_rows) == 2,
        "raw_output_not_persisted": SENSITIVE_OUTPUT.encode("utf-8") not in evaluation_bytes,
        "references_unchanged": before == after,
    }
    payload: dict[str, object] = {
        "schema_version": "okcanvas-step012-acceptance-v1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "started_at": started_at,
        "completed_at": _now(),
        "checks": checks,
        "run_id": run_id,
        "artifact_id": artifact_id,
        "evaluation_id": direct.evaluation.evaluation_id,
        "history_count": final_total,
    }
    payload = workspace.finalize(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP012_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
