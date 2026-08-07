from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.compatibility.source_contracts import component_asset_root, read_component_source
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.domain.runs.models import RunStatus, TaskStatus

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step015-admin-key-123456"
HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}


def _app(tmp_path: Path):
    return create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        evaluation_db=tmp_path / "evaluation.sqlite3",
        admin_key=ADMIN_KEY,
    )


def _seed(app) -> tuple[str, str]:
    store = app.state.product_store
    task = store.create_task(
        task_type="GENERIC_AGENT",
        input_sha256=hashlib.sha256(b"console fixture").hexdigest(),
        agent_definition_id="coding-agent",
        agent_definition_version="1.0.0",
    )
    run = store.create_run(task_id=task.task_id)
    store.transition_task(task.task_id, TaskStatus.RUNNING)
    store.transition_run(run.run_id, RunStatus.RUNNING, event_type="run.started")
    store.update_run_execution_metadata(
        run.run_id,
        trace_id="trace_console_fixture",
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
    )
    store.transition_run(run.run_id, RunStatus.SUCCEEDED, event_type="run.completed")
    store.transition_task(task.task_id, TaskStatus.SUCCEEDED)
    return task.task_id, run.run_id


def test_operations_console_shell_contains_no_admin_secret(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with TestClient(app) as client:
        response = client.get("/console")
        assert response.status_code == 200
        assert "READ-ONLY CONSOLE" in response.text
        assert ADMIN_KEY not in response.text
        assert "default-src 'self'" in response.headers["content-security-policy"]
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/console/assets/console.js").status_code == 200
        assert client.get("/console/assets/persisted-sse.js").status_code == 200
        assert client.get("/console/assets/console.css").status_code == 200


def test_operations_summary_and_lists_require_auth_and_are_read_only(tmp_path: Path) -> None:
    app = _app(tmp_path)
    task_id, run_id = _seed(app)
    product_sha_before = hashlib.sha256((tmp_path / "product.sqlite3").read_bytes()).hexdigest()
    evaluation_sha_before = hashlib.sha256((tmp_path / "evaluation.sqlite3").read_bytes()).hexdigest()

    with TestClient(app) as client:
        assert client.get("/v1/operations/summary").status_code == 401
        summary_response = client.get("/v1/operations/summary", headers=HEADERS)
        assert summary_response.status_code == 200
        summary = summary_response.json()
        assert summary["runtime"]["console_mode"] == "read-only"
        assert summary["product"]["task_total"] == 1
        assert summary["product"]["run_total"] == 1
        assert summary["product"]["run_status_counts"]["SUCCEEDED"] == 1
        assert summary["catalog"]["agent_definition_total"] == 32
        assert summary["catalog"]["mcp_server_total"] == 3
        assert summary["references"]["verified"] == summary["references"]["total"] == 4
        assert summary["recent_runs"][0]["run_id"] == run_id

        tasks = client.get("/v1/tasks?status=SUCCEEDED", headers=HEADERS).json()
        assert tasks["total"] == 1
        assert tasks["tasks"][0]["task_id"] == task_id
        runs = client.get("/v1/runs?status=SUCCEEDED&agent_definition_id=coding-agent", headers=HEADERS).json()
        assert runs["total"] == 1
        assert runs["runs"][0]["run_id"] == run_id
        assert client.get("/v1/runs?status=BOGUS", headers=HEADERS).status_code == 422

    assert hashlib.sha256((tmp_path / "product.sqlite3").read_bytes()).hexdigest() == product_sha_before
    assert hashlib.sha256((tmp_path / "evaluation.sqlite3").read_bytes()).hexdigest() == evaluation_sha_before


def test_console_javascript_uses_only_get_for_product_api() -> None:
    script = (component_asset_root(ROOT, "operations_console.assets") / "console.js").read_text(encoding="utf-8")
    assert 'method:"GET"' in script
    assert 'method:"POST"' not in script
    assert 'method:"PATCH"' not in script
    assert 'method:"DELETE"' not in script
    assert "localStorage" not in script
    assert "sessionStorage" in script
    assert "OPENAI_API_KEY" not in script
