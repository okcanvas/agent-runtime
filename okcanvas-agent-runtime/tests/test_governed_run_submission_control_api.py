from __future__ import annotations

import base64
import json
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import GatewayLifecycleEvent, GenericGatewayRunResult

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step018-read-admin-key-123456"
SUBMITTER_KEY = "step018-run-submitter-key-123456"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SUBMIT_HEADERS = {
    **ADMIN_HEADERS,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
}
RAW_REQUEST = "STEP018 governed raw request sentinel"


class SuccessfulGateway:
    calls = 0

    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        self.calls += 1
        assert request == RAW_REQUEST
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        await lifecycle_sink(GatewayLifecycleEvent("model.completed", {"response_id": "resp_governed"}))
        await lifecycle_sink(GatewayLifecycleEvent("agent.completed", {"output_contract": definition.output_contract}))
        return GenericGatewayRunResult(
            output=CodingAgentResult(
                status=AgentStatus.PASS,
                summary="Governed execution completed.",
                findings=[],
                unverified=[],
            ),
            usage=UsageSummary(requests=1, input_tokens=7, output_tokens=3, total_tokens=10),
            trace_id="trace_governed",
            response_id="resp_governed",
            sdk_version="0.19.0",
        )


def _app(tmp_path: Path, gateway=None):
    return create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key=ADMIN_KEY,
        gateway=gateway or SuccessfulGateway(),
        run_submitter_key=SUBMITTER_KEY,
        protected_payload_root=tmp_path / "protected-payloads",
        protected_payload_key=PAYLOAD_KEY,
    )


def _preflight(client: TestClient, key: str = "step018-api-idempotency-0001") -> dict:
    response = client.post(
        "/v1/run-submissions/preflight",
        headers=SUBMIT_HEADERS,
        json={
            "agent_definition_id": "coding-agent",
            "input": RAW_REQUEST,
            "model": "test-model",
            "idempotency_key": key,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _wait_terminal(client: TestClient, run_id: str) -> dict:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        payload = client.get(f"/v1/runs/{run_id}", headers=ADMIN_HEADERS).json()
        if payload["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return payload
        time.sleep(0.02)
    raise AssertionError("governed run did not become terminal")


def test_governed_preflight_requires_separate_submitter_authority(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        denied = client.post(
            "/v1/run-submissions/preflight",
            headers=ADMIN_HEADERS,
            json={
                "agent_definition_id": "coding-agent",
                "input": RAW_REQUEST,
                "model": "test-model",
                "idempotency_key": "step018-api-idempotency-0001",
            },
        )
    assert denied.status_code == 403
    assert denied.json()["code"] == "RUN_SUBMITTER_AUTHORITY_REQUIRED"


def test_preflight_encrypts_and_confirm_creates_exactly_one_task_run(tmp_path: Path) -> None:
    gateway = SuccessfulGateway()
    with TestClient(_app(tmp_path, gateway)) as client:
        submission = _preflight(client)
        assert submission["protected_payload_persisted"] is True
        assert submission["task_id"] is None
        assert submission["run_id"] is None
        wrong = client.post(
            f"/v1/run-submissions/{submission['submission_id']}/confirm",
            headers=SUBMIT_HEADERS,
            json={"confirmation": submission["confirmation_challenge"] + "x"},
        )
        assert wrong.status_code == 409
        assert wrong.json()["code"] == "RUN_SUBMISSION_CONFIRMATION_INVALID"

        confirmed = client.post(
            f"/v1/run-submissions/{submission['submission_id']}/confirm",
            headers=SUBMIT_HEADERS,
            json={"confirmation": submission["confirmation_challenge"]},
        )
        assert confirmed.status_code == 202, confirmed.text
        first = confirmed.json()
        assert first["scheduled"] is True
        assert first["replayed"] is False

        replay = client.post(
            f"/v1/run-submissions/{submission['submission_id']}/confirm",
            headers=SUBMIT_HEADERS,
            json={"confirmation": submission["confirmation_challenge"]},
        )
        assert replay.status_code == 202
        second = replay.json()
        assert second["task_id"] == first["task_id"]
        assert second["run_id"] == first["run_id"]
        assert second["scheduled"] is False
        assert second["replayed"] is True

        terminal = _wait_terminal(client, first["run_id"])
        assert terminal["status"] == "SUCCEEDED"
        task = client.get(f"/v1/tasks/{first['task_id']}", headers=ADMIN_HEADERS).json()
        assert task["status"] == "SUCCEEDED"
        detail = client.get(
            f"/v1/run-submissions/{submission['submission_id']}", headers=ADMIN_HEADERS
        ).json()
        assert detail["task_id"] == first["task_id"]
        assert detail["run_id"] == first["run_id"]
        assert detail["protected_payload_ref"] == submission["protected_payload_ref"]

    connection = sqlite3.connect(tmp_path / "product.sqlite3")
    try:
        assert connection.execute("SELECT COUNT(*) FROM task").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM run").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM run_submission_preflight").fetchone()[0] == 1
        task_payload_ref = connection.execute("SELECT protected_payload_ref FROM task").fetchone()[0]
        assert task_payload_ref == submission["protected_payload_ref"]
    finally:
        connection.close()
    database = (tmp_path / "product.sqlite3").read_bytes()
    assert not list((tmp_path / "protected-payloads").glob("payload_*.json"))
    assert detail["payload_retention_state"] == "DELETED"
    assert detail["payload_deleted_at"] is not None
    assert RAW_REQUEST.encode() not in database
    assert SUBMITTER_KEY.encode() not in database
    assert PAYLOAD_KEY.encode() not in database
    assert gateway.calls == 1


def test_tampered_payload_blocks_task_run_creation(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        submission = _preflight(client, "step018-api-idempotency-tamper")
        path = tmp_path / "protected-payloads" / f"{submission['protected_payload_ref']}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["ciphertext_b64"] = payload["ciphertext_b64"][:-2] + "AA"
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        response = client.post(
            f"/v1/run-submissions/{submission['submission_id']}/confirm",
            headers=SUBMIT_HEADERS,
            json={"confirmation": submission["confirmation_challenge"]},
        )
        assert response.status_code == 409
        assert response.json()["code"] == "PROTECTED_PAYLOAD_INTEGRITY_FAILED"
    connection = sqlite3.connect(tmp_path / "product.sqlite3")
    try:
        assert connection.execute("SELECT COUNT(*) FROM task").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM run").fetchone()[0] == 0
    finally:
        connection.close()


def test_unconfigured_server_keeps_read_api_but_disables_submission(tmp_path: Path) -> None:
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key=ADMIN_KEY,
        gateway=SuccessfulGateway(),
    )
    with TestClient(app) as client:
        policy = client.get("/v1/run-submission-policy", headers=ADMIN_HEADERS)
        denied = client.post(
            "/v1/run-submissions/preflight",
            headers={**ADMIN_HEADERS, "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY},
            json={
                "agent_definition_id": "coding-agent",
                "input": RAW_REQUEST,
                "model": "test-model",
                "idempotency_key": "step018-api-idempotency-disabled",
            },
        )
    assert policy.status_code == 200
    assert denied.status_code == 503
    assert denied.json()["code"] == "RUN_SUBMISSION_NOT_CONFIGURED"


def test_admin_and_submitter_keys_must_be_distinct(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        create_app(
            project_root=ROOT,
            product_db=tmp_path / "product.sqlite3",
            artifact_root=tmp_path / "artifacts",
            admin_key=ADMIN_KEY,
            run_submitter_key=ADMIN_KEY,
            protected_payload_root=tmp_path / "protected",
            protected_payload_key=PAYLOAD_KEY,
        )
