from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.domain.runs.models import EventSource, RunStatus, TaskStatus
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step016-acceptance-admin-key"
HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_acceptance(output: Path) -> int:
    with AcceptanceWorkspace(step_id="STEP016", output=output) as workspace:
        product_db = workspace.database_dir / "product.sqlite3"
        evaluation_db = workspace.database_dir / "evaluation.sqlite3"
        app = create_app(
            project_root=ROOT,
            product_db=product_db,
            artifact_root=workspace.artifact_dir,
            evaluation_db=evaluation_db,
            admin_key=ADMIN_KEY,
        )
        store = app.state.product_store
        task = store.create_task(
            task_type="GENERIC_AGENT",
            input_sha256=hashlib.sha256(b"step016 fixture").hexdigest(),
            agent_definition_id="coding-agent",
            agent_definition_version="1.0.0",
        )
        run = store.create_run(task_id=task.task_id)
        store.transition_task(task.task_id, TaskStatus.RUNNING)
        store.transition_run(run.run_id, RunStatus.RUNNING, event_type="run.started")
        store.append_event(
            run.run_id,
            event_type="model.started",
            source=EventSource.AGENT_SDK,
            payload={"model_present": True},
        )
        store.append_event(
            run.run_id,
            event_type="model.completed",
            source=EventSource.AGENT_SDK,
            payload={"usage_present": True},
        )
        store.transition_run(run.run_id, RunStatus.SUCCEEDED, event_type="run.completed")
        store.transition_task(task.task_id, TaskStatus.SUCCEEDED)
        product_before = _sha(product_db)
        evaluation_before = _sha(evaluation_db)
        reference_before = {
            item.reference_id: item.to_dict()
            for item in ReferenceCatalogService(ROOT).verify_all()
        }

        with TestClient(app) as client:
            shell = client.get("/console")
            console_js = client.get("/console/assets/console.js")
            parser_js = client.get("/console/assets/persisted-sse.js")
            unauth = client.get(f"/v1/runs/{run.run_id}/events/stream")
            with client.stream(
                "GET",
                f"/v1/runs/{run.run_id}/events/stream?cursor=2",
                headers={**HEADERS, "Last-Event-ID": "3"},
            ) as response:
                stream_body = "".join(response.iter_text())
                stream_headers = dict(response.headers)
                stream_status = response.status_code

        script = console_js.text
        parser = parser_js.text
        reference_after = {
            item.reference_id: item.to_dict()
            for item in ReferenceCatalogService(ROOT).verify_all()
        }
        checks = {
            "console_shell_served": shell.status_code == 200,
            "live_assets_served": console_js.status_code == 200 and parser_js.status_code == 200,
            "live_controls_present": all(token in shell.text for token in ("runLiveBadge", "runCursor", "runAutoFollow", "reconnectRunButton", "stopRunButton")),
            "authenticated_fetch_sse": "OKCanvasPersistedSSE.stream" in script and '"X-OKCanvas-Admin-Key":state.key' in script,
            "native_eventsource_rejected": "EventSource" not in script + parser,
            "cursor_and_last_event_id_used": "/events/stream?cursor=" in script and '"Last-Event-ID":String(cursor)' in script,
            "duplicate_sequence_guarded": "state.live.events.has(event.sequence)" in script,
            "prior_stream_aborted": "AbortController" in script and "state.live.controller.abort()" in script,
            "terminal_run_stops_reconnect": "TERMINAL_RUN_STATUSES" in script,
            "bounded_reconnect_backoff": "Math.min(5000" in script,
            "console_remains_get_only": all(token not in script + parser for token in ('method:"POST"', 'method:"PATCH"', 'method:"DELETE"')),
            "stream_auth_required": unauth.status_code == 401,
            "stream_resumed_after_effective_cursor": stream_status == 200 and "id: 3" not in stream_body and "id: 4" in stream_body,
            "terminal_event_streamed": "event: run.completed" in stream_body,
            "stream_headers_disable_buffering": stream_headers.get("cache-control") == "no-cache, no-transform" and stream_headers.get("x-accel-buffering") == "no",
            "admin_key_not_embedded": ADMIN_KEY not in shell.text + script + parser,
            "product_db_unchanged_by_live_reads": _sha(product_db) == product_before,
            "evaluation_db_unchanged_by_live_reads": _sha(evaluation_db) == evaluation_before,
            "references_unchanged": reference_before == reference_after,
        }
        payload: dict[str, object] = {
            "schema_version": "okcanvas-step016-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "run_id": run.run_id,
            "task_id": task.task_id,
            "effective_resume_cursor": 3,
            "streamed_event_ids": [4, 5],
        }
        payload = workspace.finalize(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP016_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
