from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import GatewayLifecycleEvent, GenericGatewayRunResult
from okcanvas_agent_runtime.domain.runs import EventSource, RunStatus, TaskStatus
from tests.artifact_test_support import artifact_service

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "interactive-runner-admin-key"
SUBMITTER_KEY = "interactive-runner-submitter-key"


class ReferenceGateway:
    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        for tool_name in ("search_reference", "read_reference_file"):
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "tool.started",
                    {"server_id": "reference-catalog", "tool_name": tool_name},
                    source=EventSource.MCP,
                )
            )
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "tool.completed",
                    {"server_id": "reference-catalog", "tool_name": tool_name},
                    source=EventSource.MCP,
                )
            )
        await lifecycle_sink(GatewayLifecycleEvent("model.completed", {"response_id": "resp"}))
        await lifecycle_sink(GatewayLifecycleEvent("agent.completed", {"agent_id": definition.agent_id}))
        return GenericGatewayRunResult(
            output=CodingAgentResult(
                status=AgentStatus.PARTIAL,
                summary="Interactive Runner completed.",
                findings=[],
                unverified=[],
            ),
            usage=UsageSummary(requests=1, input_tokens=10, output_tokens=5, total_tokens=15),
            trace_id="trace-runner",
            response_id="resp-runner",
            sdk_version="0.19.0",
        )


def _app(tmp_path: Path):
    return create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        evaluation_db=tmp_path / "evaluation.sqlite3",
        admin_key=ADMIN_KEY,
        run_submitter_key=SUBMITTER_KEY,
        protected_payload_root=tmp_path / "payloads",
        protected_payload_key="AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=",
        gateway=ReferenceGateway(),
    )


def test_interactive_runner_static_surface_is_separate_and_governed(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        shell = client.get("/runner")
        css = client.get("/runner/assets/runner.css")
        js = client.get("/runner/assets/runner.js")
        parser = client.get("/runner/assets/persisted-sse.js")

    combined = shell.text + js.text + parser.text
    assert shell.status_code == css.status_code == js.status_code == parser.status_code == 200
    assert "default-src 'self'" in shell.headers["content-security-policy"]
    assert "X-OKCanvas-Admin-Key" in shell.text
    assert "X-OKCanvas-Run-Submitter-Key" in shell.text
    assert "sessionStorage" in js.text
    assert "localStorage" not in combined
    assert ADMIN_KEY not in combined and SUBMITTER_KEY not in combined
    assert "/v1/sessions" in js.text
    assert "session_id" in js.text
    assert "SQLite Session" in shell.text
    assert "/v1/run-submissions/preflight" in js.text
    assert "/confirm" in js.text
    assert "/prepare-approval" in js.text
    assert "/events/stream?cursor=" in js.text
    assert "/artifact" in js.text
    assert "/evaluations" in js.text
    assert "/decision" not in js.text
    assert "api('/v1/runs'" not in js.text
    assert "Operations Console" in shell.text


def test_run_artifact_api_returns_verified_content_without_storage_path(tmp_path: Path) -> None:
    app = _app(tmp_path)
    store = app.state.product_store
    task = store.create_task(
        task_type="TEST",
        input_sha256=hashlib.sha256(b"input").hexdigest(),
        agent_definition_id="coding-agent",
        agent_definition_version="1.0.0",
    )
    run = store.create_run(task_id=task.task_id)
    store.transition_task(task.task_id, TaskStatus.RUNNING)
    store.transition_run(run.run_id, RunStatus.RUNNING, event_type="run.started")
    artifact = artifact_service(store, tmp_path / "artifacts").create_json(
        run_id=run.run_id,
        artifact_type="agent.final-output",
        payload={"status": "PASS", "summary": "verified"},
    )
    store.append_event(
        run.run_id,
        event_type="artifact.created",
        source=EventSource.RUNTIME,
        payload={"artifact_id": artifact.artifact_id},
    )
    with TestClient(app) as client:
        response = client.get(
            f"/v1/runs/{run.run_id}/artifact",
            headers={"X-OKCanvas-Admin-Key": ADMIN_KEY},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["artifact_id"] == artifact.artifact_id
    assert body["content"] == {"status": "PASS", "summary": "verified"}
    assert "storage_path" not in body
