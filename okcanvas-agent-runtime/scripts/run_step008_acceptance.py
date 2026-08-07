from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.transport.admin.sse.stream import persisted_event_stream
from okcanvas_agent_runtime.application.execution import GatewayLifecycleEvent, GenericGatewayRunResult
from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step008-local-admin-key-123456"
HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
REQUEST_SENTINEL = "STEP008 raw request sentinel must not be stored"
API_KEY_SENTINEL = "step008-api-key-sentinel"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


class AcceptanceGateway:
    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        await lifecycle_sink(GatewayLifecycleEvent("model.completed", {"response_id": "resp_step008"}))
        await lifecycle_sink(GatewayLifecycleEvent("agent.completed", {"output_contract": definition.output_contract}))
        return GenericGatewayRunResult(
            output=CodingAgentResult(
                status=AgentStatus.PASS,
                summary="STEP008 deterministic API acceptance completed.",
                findings=[],
                unverified=["Live network server and live model"],
            ),
            usage=UsageSummary(requests=1, input_tokens=30, output_tokens=12, total_tokens=42),
            trace_id="trace_step008_acceptance",
            response_id="resp_step008",
            sdk_version="0.19.0-test-double",
        )


class BlockingGateway:
    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await asyncio.Event().wait()


def _wait_terminal(client: TestClient, run_id: str, timeout: float = 3.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        payload = client.get(f"/v1/runs/{run_id}", headers=HEADERS).json()
        if payload["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return payload
        time.sleep(0.02)
    raise AssertionError("run did not reach a terminal state")


async def _heartbeat_check(database: Path) -> bool:
    store = SQLiteProductStore(database)
    store.initialize()
    task = store.create_task(
        task_type="HEARTBEAT_TEST",
        input_sha256="0" * 64,
        agent_definition_id="coding-agent",
        agent_definition_version="1.0.0",
    )
    run = store.create_run(task_id=task.task_id)
    stream = persisted_event_stream(
        store=store,
        run_id=run.run_id,
        after_sequence=1,
        poll_interval_seconds=0.001,
        heartbeat_seconds=0.001,
    )
    value = await anext(stream)
    await stream.aclose()
    return value == ": heartbeat\n\n"


def run_acceptance(output: Path) -> int:
    started_at = _utc_now()
    before = {item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()}
    with AcceptanceWorkspace(step_id="STEP008", output=output) as workspace:
        root = workspace.root
        product_db = root / "product.sqlite3"
        artifacts = root / "artifacts"
        app = create_app(
            project_root=ROOT,
            product_db=product_db,
            artifact_root=artifacts,
            admin_key=ADMIN_KEY,
            gateway=AcceptanceGateway(),
            direct_run_submission_enabled=True,
        )
        import os

        previous_api_key = os.environ.get("OPENAI_API_KEY")
        previous_model = os.environ.get("OKCANVAS_AGENT_MODEL")
        os.environ["OPENAI_API_KEY"] = API_KEY_SENTINEL
        os.environ["OKCANVAS_AGENT_MODEL"] = "acceptance-model"
        try:
            with TestClient(app) as client:
                unauthorized = client.get("/v1/runs/missing")
                created_response = client.post(
                    "/v1/runs",
                    headers=HEADERS,
                    json={"input": REQUEST_SENTINEL, "confirm_live_call": True},
                )
                created = created_response.json()
                run = _wait_terminal(client, str(created["run_id"]))
                task = client.get(f"/v1/tasks/{created['task_id']}", headers=HEADERS).json()
                events = client.get(
                    f"/v1/runs/{created['run_id']}/events", headers=HEADERS
                ).json()["events"]
                outcome = client.get(
                    f"/v1/runs/{created['run_id']}/outcome", headers=HEADERS
                )
                with client.stream(
                    "GET",
                    f"/v1/runs/{created['run_id']}/events/stream",
                    headers={**HEADERS, "Last-Event-ID": "5"},
                ) as stream_response:
                    sse_body = "".join(stream_response.iter_text())
                validation_error = client.post(
                    "/v1/runs", headers=HEADERS, json={"input": ""}
                )
        finally:
            if previous_api_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = previous_api_key
            if previous_model is None:
                os.environ.pop("OKCANVAS_AGENT_MODEL", None)
            else:
                os.environ["OKCANVAS_AGENT_MODEL"] = previous_model

        cancel_db = root / "cancel.sqlite3"
        cancel_app = create_app(
            project_root=ROOT,
            product_db=cancel_db,
            artifact_root=root / "cancel-artifacts",
            admin_key=ADMIN_KEY,
            gateway=BlockingGateway(),
            direct_run_submission_enabled=True,
        )
        os.environ["OPENAI_API_KEY"] = API_KEY_SENTINEL
        os.environ["OKCANVAS_AGENT_MODEL"] = "acceptance-model"
        try:
            with TestClient(cancel_app) as client:
                cancel_created = client.post(
                    "/v1/runs",
                    headers=HEADERS,
                    json={"input": "cancel acceptance", "confirm_live_call": True},
                ).json()
                cancel_response = client.post(
                    f"/v1/runs/{cancel_created['run_id']}/cancel", headers=HEADERS
                )
                cancelled = cancel_response.json()
                cancel_events = client.get(
                    f"/v1/runs/{cancel_created['run_id']}/events", headers=HEADERS
                ).json()["events"]
        finally:
            if previous_api_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = previous_api_key
            if previous_model is None:
                os.environ.pop("OKCANVAS_AGENT_MODEL", None)
            else:
                os.environ["OKCANVAS_AGENT_MODEL"] = previous_model

        database_bytes = product_db.read_bytes()
        event_sequences = [item["sequence"] for item in events]
        event_types = [item["event_type"] for item in events]
        checks = {
            "unauthorized_rejected": unauthorized.status_code == 401,
            "run_create_accepted": created_response.status_code == 202,
            "task_succeeded": task["status"] == "SUCCEEDED",
            "run_succeeded": run["status"] == "SUCCEEDED",
            "outcome_http_200": outcome.status_code == 200,
            "events_persisted": event_types[-1] == "run.completed",
            "event_sequences_monotonic": event_sequences == list(range(1, len(events) + 1)),
            "sse_cursor_resumed": "id: 6" in sse_body and "id: 5" not in sse_body,
            "sse_terminal_completed": "event: run.completed" in sse_body,
            "heartbeat_supported": asyncio.run(_heartbeat_check(root / "heartbeat.sqlite3")),
            "cancellation_persisted": cancel_response.status_code == 200
            and cancelled["run_status"] == "CANCELLED"
            and cancel_events[-1]["event_type"] == "run.cancelled",
            "validation_error_canonical": validation_error.status_code == 422
            and validation_error.json()["code"] == "REQUEST_VALIDATION_FAILED",
            "sdk_event_classes_not_public": "RawResponsesStreamEvent" not in json.dumps(events),
            "raw_request_not_in_database": REQUEST_SENTINEL.encode() not in database_bytes,
            "api_key_not_in_database": API_KEY_SENTINEL.encode() not in database_bytes,
            "admin_key_not_in_database": ADMIN_KEY.encode() not in database_bytes,
        }
        result: dict[str, object] = {
            "schema_version": "okcanvas-step008-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "started_at": started_at,
            "completed_at": _utc_now(),
            "checks": checks,
            "created": created,
            "task": task,
            "run": run,
            "event_types": event_types,
            "sse_after_sequence": 5,
            "cancelled": cancelled,
        }
    after = {item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()}
    result["checks"]["references_unchanged"] = before == after  # type: ignore[index]
    result["reference_verification_before"] = before
    result["reference_verification_after"] = after
    result["state"] = "PASSED" if all(result["checks"].values()) else "FAILED"  # type: ignore[union-attr]
    result = workspace.finalize(result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/evidence/STEP008_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
