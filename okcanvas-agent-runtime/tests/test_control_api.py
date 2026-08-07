from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import GatewayLifecycleEvent, GenericGatewayRunResult

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "test-local-admin-key-123456"
HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}


class SuccessfulGateway:
    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        await lifecycle_sink(GatewayLifecycleEvent("model.completed", {"response_id": "resp_api"}))
        await lifecycle_sink(GatewayLifecycleEvent("agent.completed", {"output_contract": definition.output_contract}))
        return GenericGatewayRunResult(
            output=CodingAgentResult(
                status=AgentStatus.PASS,
                summary="API execution completed.",
                findings=[],
                unverified=[],
            ),
            usage=UsageSummary(requests=1, input_tokens=10, output_tokens=5, total_tokens=15),
            trace_id="trace_api",
            response_id="resp_api",
            sdk_version="0.19.0",
        )


class BlockingGateway:
    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await asyncio.Event().wait()


def _app(tmp_path: Path, gateway):
    return create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key=ADMIN_KEY,
        gateway=gateway,
        direct_run_submission_enabled=True,
    )


def _wait_terminal(client: TestClient, run_id: str, timeout: float = 3.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers=HEADERS)
        payload = response.json()
        if payload["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return payload
        time.sleep(0.02)
    raise AssertionError("run did not reach a terminal state")


def test_api_requires_local_admin_authentication(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OKCANVAS_AGENT_MODEL", "test-model")
    with TestClient(_app(tmp_path, SuccessfulGateway())) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/v1/runs/missing").status_code == 401


def test_create_read_events_and_persisted_sse_resume(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OKCANVAS_AGENT_MODEL", "test-model")
    with TestClient(_app(tmp_path, SuccessfulGateway())) as client:
        created = client.post(
            "/v1/runs",
            headers=HEADERS,
            json={
                "agent_definition_id": "coding-agent",
                "input": "Analyze supplied text",
                "confirm_live_call": True,
            },
        )
        assert created.status_code == 202
        ids = created.json()
        run = _wait_terminal(client, ids["run_id"])
        assert run["status"] == "SUCCEEDED"
        assert run["trace_id"] == "trace_api"
        task = client.get(f"/v1/tasks/{ids['task_id']}", headers=HEADERS)
        assert task.json()["status"] == "SUCCEEDED"

        events = client.get(f"/v1/runs/{ids['run_id']}/events", headers=HEADERS).json()["events"]
        assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
        assert events[-1]["event_type"] == "run.completed"
        assert all("RawResponsesStreamEvent" not in json.dumps(item) for item in events)

        with client.stream(
            "GET",
            f"/v1/runs/{ids['run_id']}/events/stream",
            headers={**HEADERS, "Last-Event-ID": "5"},
        ) as response:
            body = "".join(response.iter_text())
        assert response.status_code == 200
        assert "id: 6" in body
        assert "id: 5" not in body
        assert "event: run.completed" in body


def test_http_error_status_matches_preflight_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OKCANVAS_AGENT_MODEL", "test-model")
    with TestClient(_app(tmp_path, SuccessfulGateway())) as client:
        response = client.post(
            "/v1/runs",
            headers=HEADERS,
            json={"input": "work", "confirm_live_call": False},
        )
        assert response.status_code == 409
        assert response.json()["code"] == "LIVE_OPT_IN_REQUIRED"


def test_cancel_records_terminal_product_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OKCANVAS_AGENT_MODEL", "test-model")
    with TestClient(_app(tmp_path, BlockingGateway())) as client:
        created = client.post(
            "/v1/runs",
            headers=HEADERS,
            json={"input": "block", "confirm_live_call": True},
        ).json()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            events = client.get(
                f"/v1/runs/{created['run_id']}/events", headers=HEADERS
            ).json()["events"]
            if any(item["event_type"] == "agent.started" for item in events):
                break
            time.sleep(0.02)
        response = client.post(f"/v1/runs/{created['run_id']}/cancel", headers=HEADERS)
        assert response.status_code == 200
        assert response.json()["run_status"] == "CANCELLED"
        assert response.json()["task_status"] == "CANCELLED"
        event_types = [
            item["event_type"]
            for item in client.get(
                f"/v1/runs/{created['run_id']}/events", headers=HEADERS
            ).json()["events"]
        ]
        assert event_types[-1] == "run.cancelled"
        assert client.post(f"/v1/runs/{created['run_id']}/cancel", headers=HEADERS).status_code == 409



def test_outcome_endpoint_maps_terminal_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OKCANVAS_AGENT_MODEL", "test-model")
    with TestClient(_app(tmp_path, SuccessfulGateway())) as client:
        created = client.post(
            "/v1/runs",
            headers=HEADERS,
            json={"input": "outcome", "confirm_live_call": True},
        ).json()
        _wait_terminal(client, created["run_id"])
        response = client.get(f"/v1/runs/{created['run_id']}/outcome", headers=HEADERS)
        assert response.status_code == 200
        assert response.json()["status"] == "SUCCEEDED"


def test_validation_error_uses_canonical_contract(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OKCANVAS_AGENT_MODEL", "test-model")
    with TestClient(_app(tmp_path, SuccessfulGateway())) as client:
        response = client.post("/v1/runs", headers=HEADERS, json={"input": ""})
        assert response.status_code == 422
        assert response.json()["schema_version"] == "okcanvas-control-error-v1"
        assert response.json()["code"] == "REQUEST_VALIDATION_FAILED"


def test_failed_sdk_outcome_maps_to_bad_gateway(tmp_path: Path, monkeypatch) -> None:
    from okcanvas_agent_runtime.application.execution import GenericExecutionErrorCode
    from okcanvas_agent_runtime.application.execution.errors import GenericExecutionFailure

    class FailedGateway:
        async def run(self, **kwargs):
            raise GenericExecutionFailure(
                GenericExecutionErrorCode.SDK_RUN_FAILED,
                "SDK failed",
                retryable=True,
                detail_type="ModelBehaviorError",
            )

    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OKCANVAS_AGENT_MODEL", "test-model")
    with TestClient(_app(tmp_path, FailedGateway())) as client:
        created = client.post(
            "/v1/runs",
            headers=HEADERS,
            json={"input": "fail", "confirm_live_call": True},
        ).json()
        run = _wait_terminal(client, created["run_id"])
        assert run["status"] == "FAILED"
        outcome = client.get(f"/v1/runs/{created['run_id']}/outcome", headers=HEADERS)
        assert outcome.status_code == 502
        assert outcome.json()["code"] == "SDK_RUN_FAILED"
        assert outcome.json()["retryable"] is True
        assert outcome.json()["details"] == {"detail_type": "ModelBehaviorError"}
