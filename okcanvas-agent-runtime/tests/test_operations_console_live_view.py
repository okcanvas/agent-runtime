from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from okcanvas_agent_runtime.compatibility.source_contracts import component_asset_root, read_component_source
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.domain.runs.models import EventSource, RunStatus, TaskStatus

ROOT = Path(__file__).resolve().parents[1]
ASSETS = component_asset_root(ROOT, "operations_console.assets")
ADMIN_KEY = "step016-admin-key-123456"
HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}


def _app(tmp_path: Path):
    return create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        evaluation_db=tmp_path / "evaluation.sqlite3",
        admin_key=ADMIN_KEY,
    )


def _terminal_run(app) -> str:
    store = app.state.product_store
    task = store.create_task(
        task_type="GENERIC_AGENT",
        input_sha256="0" * 64,
        agent_definition_id="coding-agent",
        agent_definition_version="1.0.0",
    )
    run = store.create_run(task_id=task.task_id)
    store.transition_task(task.task_id, TaskStatus.RUNNING)
    store.transition_run(run.run_id, RunStatus.RUNNING, event_type="run.started")
    store.append_event(run.run_id, event_type="model.started", source=EventSource.AGENT_SDK, payload={})
    store.append_event(run.run_id, event_type="model.completed", source=EventSource.AGENT_SDK, payload={})
    store.transition_run(run.run_id, RunStatus.SUCCEEDED, event_type="run.completed")
    store.transition_task(task.task_id, TaskStatus.SUCCEEDED)
    return run.run_id


def test_console_live_view_assets_preserve_authenticated_get_only_boundary() -> None:
    html = (ASSETS / "index.html").read_text(encoding="utf-8")
    script = (ASSETS / "console.js").read_text(encoding="utf-8")
    parser = (ASSETS / "persisted-sse.js").read_text(encoding="utf-8")
    assert html.index("persisted-sse.js") < html.index("console.js")
    assert 'id="runLiveBadge"' in html
    assert 'id="runCursor"' in html
    assert 'id="runAutoFollow"' in html
    assert "/events/stream?cursor=" in script
    assert '"Last-Event-ID":String(cursor)' in script
    assert '"X-OKCanvas-Admin-Key":state.key' in script
    assert "AbortController" in script
    assert "state.live.events.has(event.sequence)" in script
    assert "EventSource" not in script
    assert 'method:"GET"' in script
    assert all(token not in script for token in ('method:"POST"', 'method:"PATCH"', 'method:"DELETE"'))
    assert 'method:"GET"' in parser
    assert "localStorage" not in script + parser
    assert "OPENAI_API_KEY" not in script + parser


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is optional and unavailable")
def test_browser_sse_parser_handles_chunk_boundaries_crlf_and_heartbeat() -> None:
    parser_path = json.dumps(str(ASSETS / "persisted-sse.js"))
    program = f"""
      require({parser_path});
      const events=[]; const comments=[];
      const parser=globalThis.OKCanvasPersistedSSE.createParser({{
        onEvent:(value)=>events.push(value), onComment:(value)=>comments.push(value)
      }});
      parser.feed('id: 7\\r\\nevent: model.com');
      parser.feed('pleted\\r\\ndata: {{"sequence":7,');
      parser.feed('"payload":{{}}}}\\r\\n\\r\\n: heart');
      parser.feed('beat\\n\\n');
      parser.feed('id: 8\\ndata: first\\ndata: second\\n\\n');
      parser.end();
      process.stdout.write(JSON.stringify({{events,comments}}));
    """
    completed = subprocess.run(
        [shutil.which("node") or "node", "-e", program],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["events"] == [
        {"id": "7", "event": "model.completed", "data": '{"sequence":7,"payload":{}}'},
        {"id": "8", "event": "message", "data": "first\nsecond"},
    ]
    assert payload["comments"] == ["heartbeat"]


def test_persisted_stream_replays_after_cursor_and_has_no_buffering_headers(tmp_path: Path) -> None:
    app = _app(tmp_path)
    run_id = _terminal_run(app)
    with TestClient(app) as client:
        with client.stream(
            "GET",
            f"/v1/runs/{run_id}/events/stream?cursor=2",
            headers={**HEADERS, "Last-Event-ID": "3"},
        ) as response:
            body = "".join(response.iter_text())
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-cache, no-transform"
        assert response.headers["x-accel-buffering"] == "no"
        assert response.headers["connection"] == "keep-alive"
        assert "id: 3" not in body
        assert "id: 4" in body
        assert "event: run.completed" in body
