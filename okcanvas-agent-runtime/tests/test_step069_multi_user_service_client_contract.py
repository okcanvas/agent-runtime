from __future__ import annotations

import base64
import hashlib
import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import GatewayLifecycleEvent, GenericGatewayRunResult

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step069-local-admin-key-123456"
SUBMITTER_KEY = "step069-local-submitter-key-123456"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_KEY = base64.urlsafe_b64encode(bytes(range(32, 64))).decode("ascii")
ALICE_TOKEN = "step069-alice-service-token-123456"
BOB_TOKEN = "step069-bob-service-token-12345678"
MALLORY_TOKEN = "step069-mallory-service-token-1234"
OPERATOR_TOKEN = "step069-operator-service-token-1234"
OTHER_OPERATOR_TOKEN = "step069-other-operator-token-123456"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


REGISTRY = json.dumps({
    "schema_version": "okcanvas-service-client-token-registry-v1",
    "tokens": [
        {"token_id": "alice-web", "token_sha256": _sha(ALICE_TOKEN), "tenant_id": "tenant-a", "principal_id": "alice", "roles": ["agent-user"]},
        {"token_id": "bob-cli", "token_sha256": _sha(BOB_TOKEN), "tenant_id": "tenant-a", "principal_id": "bob", "roles": ["agent-user"]},
        {"token_id": "mallory-web", "token_sha256": _sha(MALLORY_TOKEN), "tenant_id": "tenant-b", "principal_id": "mallory", "roles": ["agent-user"]},
        {"token_id": "ops-desktop", "token_sha256": _sha(OPERATOR_TOKEN), "tenant_id": "tenant-a", "principal_id": "operator", "roles": ["approval-operator"]},
        {"token_id": "other-ops", "token_sha256": _sha(OTHER_OPERATOR_TOKEN), "tenant_id": "tenant-b", "principal_id": "other-operator", "roles": ["approval-operator"]},
    ],
}, sort_keys=True)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class SuccessfulGateway:
    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        await lifecycle_sink(GatewayLifecycleEvent("model.completed", {"response_id": "resp_step069"}))
        await lifecycle_sink(GatewayLifecycleEvent("agent.completed", {"output_contract": definition.output_contract}))
        return GenericGatewayRunResult(
            output=CodingAgentResult(status=AgentStatus.PASS, summary="Service client run completed.", findings=[], unverified=[]),
            usage=UsageSummary(requests=1, input_tokens=8, output_tokens=4, total_tokens=12),
            trace_id="trace_step069",
            response_id="resp_step069",
            sdk_version="0.19.0",
        )


def _app(tmp_path: Path, *, tool_approval_gateway=None):
    return create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key=ADMIN_KEY,
        gateway=SuccessfulGateway(),
        run_submitter_key=SUBMITTER_KEY,
        protected_payload_root=tmp_path / "protected-payloads",
        protected_payload_key=PAYLOAD_KEY,
        session_root=tmp_path / "sessions",
        session_history_key=SESSION_KEY,
        service_client_token_registry_json=REGISTRY,
        tool_approval_gateway=tool_approval_gateway,
        run_state_root=tmp_path / "run-states",
    )


def _preflight(client: TestClient, token: str, *, key: str = "same-client-key-0001") -> dict:
    response = client.post(
        "/v1/service/run-submissions/preflight",
        headers=_headers(token),
        json={
            "agent_definition_id": "coding-agent",
            "input": "Review the service-client contract.",
            "model": "test-model",
            "idempotency_key": key,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _confirm(client: TestClient, token: str, submission: dict) -> dict:
    response = client.post(
        f"/v1/service/run-submissions/{submission['submission_id']}/confirm",
        headers=_headers(token),
        json={"confirmation": submission["confirmation_challenge"]},
    )
    assert response.status_code == 202, response.text
    return response.json()


def _wait_terminal(client: TestClient, token: str, run_id: str) -> dict:
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        response = client.get(f"/v1/service/runs/{run_id}", headers=_headers(token))
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return payload
        time.sleep(0.02)
    raise AssertionError("service-client Run did not become terminal")


def test_service_capability_and_principal_contract(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        assert client.get("/v1/service/capabilities").status_code == 401
        capabilities = client.get("/v1/service/capabilities", headers=_headers(ALICE_TOKEN))
        assert capabilities.status_code == 200
        body = capabilities.json()
        assert body["multi_user_resource_scoping"] is True
        assert body["supported_clients"] == ["agent-cli", "agent-web", "agent-desktop"]
        assert body["native_sdk_stream_exposed_to_service_clients"] is False
        assert body["runtime_internal_storage_access_allowed"] is False
        assert body["skills_available"] is True
        assert body["skill_catalog_api"] == "/v1/service/skills"
        assert body["skill_foundation_step"] == "STEP070_PRODUCT_OWNED_SKILL_PACKAGE_FOUNDATION_V1"
        assert body["next_skill_step"] is None
        from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
        assert body["next_selected_step"] == RuntimeInfo().next_selected_step
        whoami = client.get("/v1/service/whoami", headers=_headers(ALICE_TOKEN)).json()
        assert whoami == {
            "schema_version": "okcanvas-service-principal-v1",
            "token_id": "alice-web",
            "tenant_id": "tenant-a",
            "principal_id": "alice",
            "roles": ["agent-user"],
        }
        assert client.get("/v1/service/whoami", headers=_headers("wrong-token")).status_code == 401


def test_service_idempotency_is_namespaced_per_principal(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        alice = _preflight(client, ALICE_TOKEN)
        bob = _preflight(client, BOB_TOKEN)
        assert alice["submission_id"] != bob["submission_id"]
        assert alice["idempotency_key_sha256"] != bob["idempotency_key_sha256"]
        assert client.get(
            f"/v1/service/run-submissions/{alice['submission_id']}", headers=_headers(BOB_TOKEN)
        ).status_code == 404
        assert client.get(
            f"/v1/service/run-submissions/{alice['submission_id']}", headers=_headers(MALLORY_TOKEN)
        ).status_code == 404


def test_service_run_event_and_artifact_are_principal_scoped(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        submission = _preflight(client, ALICE_TOKEN, key="alice-run-contract-0001")
        confirmed = _confirm(client, ALICE_TOKEN, submission)
        run_id = confirmed["run_id"]
        terminal = _wait_terminal(client, ALICE_TOKEN, run_id)
        assert terminal["status"] == "SUCCEEDED"
        assert client.get(f"/v1/service/runs/{run_id}", headers=_headers(BOB_TOKEN)).status_code == 404
        assert client.get(f"/v1/service/runs/{run_id}", headers=_headers(MALLORY_TOKEN)).status_code == 404

        event_payload = client.get(f"/v1/service/runs/{run_id}/events", headers=_headers(ALICE_TOKEN)).json()
        assert any(item["event_type"] == "run.completed" for item in event_payload["events"])
        with client.stream(
            "GET",
            f"/v1/service/runs/{run_id}/events/stream?cursor=0",
            headers={**_headers(ALICE_TOKEN), "Last-Event-ID": "5"},
        ) as response:
            stream_text = "".join(response.iter_text())
        assert response.status_code == 200
        assert "id: 6" in stream_text
        assert "id: 5" not in stream_text

        artifacts = client.get(f"/v1/service/runs/{run_id}/artifacts", headers=_headers(ALICE_TOKEN))
        assert artifacts.status_code == 200
        artifact_list = artifacts.json()
        assert artifact_list["total"] == 1
        artifact_id = artifact_list["artifacts"][0]["artifact_id"]
        artifact = client.get(
            f"/v1/service/runs/{run_id}/artifacts/{artifact_id}", headers=_headers(ALICE_TOKEN)
        )
        assert artifact.status_code == 200
        assert artifact.json()["content"]["summary"] == "Service client run completed."
        assert client.get(
            f"/v1/service/runs/{run_id}/artifacts/{artifact_id}", headers=_headers(BOB_TOKEN)
        ).status_code == 404


def test_service_session_and_attachment_ownership_are_isolated(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        session = client.post(
            "/v1/service/sessions",
            headers=_headers(ALICE_TOKEN),
            json={"agent_definition_id": "session-continuity-agent"},
        )
        assert session.status_code == 201, session.text
        session_id = session.json()["session_id"]
        assert client.get(f"/v1/service/sessions/{session_id}", headers=_headers(ALICE_TOKEN)).status_code == 200
        assert client.get(f"/v1/service/sessions/{session_id}", headers=_headers(BOB_TOKEN)).status_code == 404

        png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (1).to_bytes(4, "big") + (1).to_bytes(4, "big") + b"\x08\x02\x00\x00\x00" + b"\x90wS\xde" + b"\x00\x00\x00\x00IEND\xaeB`\x82"
        upload = client.post(
            "/v1/service/local-attachments",
            headers={**_headers(ALICE_TOKEN), "X-OKCanvas-Attachment-Filename": "pixel.png"},
            content=png,
        )
        assert upload.status_code == 201, upload.text
        attachment_id = upload.json()["attachment_id"]
        denied = client.post(
            "/v1/service/run-submissions/preflight",
            headers=_headers(BOB_TOKEN),
            json={
                "agent_definition_id": "local-document-review-agent",
                "input": "Review the image.",
                "model": "gpt-4.1",
                "attachment_id": attachment_id,
                "idempotency_key": "bob-cannot-use-alice-file-0001",
            },
        )
        assert denied.status_code == 404



def test_service_approval_operator_is_tenant_scoped(tmp_path: Path, monkeypatch) -> None:
    from okcanvas_agent_runtime.application.approvals import decision_confirmation_challenge
    from okcanvas_agent_runtime.application.approvals.testing import DeterministicToolApprovalGateway

    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    with TestClient(_app(tmp_path, tool_approval_gateway=DeterministicToolApprovalGateway())) as client:
        response = client.post(
            "/v1/service/run-submissions/preflight",
            headers=_headers(ALICE_TOKEN),
            json={
                "agent_definition_id": "local-text-metrics-agent",
                "input": "Count bounded words for tenant approval.",
                "model": "acceptance-model",
                "idempotency_key": "tenant-approval-service-0001",
            },
        )
        assert response.status_code == 201, response.text
        submission = response.json()
        prepared = client.post(
            f"/v1/service/run-submissions/{submission['submission_id']}/prepare-approval",
            headers=_headers(ALICE_TOKEN),
        )
        assert prepared.status_code == 202, prepared.text
        approval = prepared.json()
        assert client.get("/v1/service/tool-approvals", headers=_headers(ALICE_TOKEN)).status_code == 403
        assert client.get("/v1/service/tool-approvals", headers=_headers(OTHER_OPERATOR_TOKEN)).json()["total"] == 0
        inbox = client.get("/v1/service/tool-approvals", headers=_headers(OPERATOR_TOKEN))
        assert inbox.status_code == 200
        assert inbox.json()["total"] == 1
        denied = client.get(
            f"/v1/service/tool-approvals/{approval['approval_id']}/inbox",
            headers=_headers(OTHER_OPERATOR_TOKEN),
        )
        assert denied.status_code == 404
        decided = client.post(
            f"/v1/service/tool-approvals/{approval['approval_id']}/decision",
            headers=_headers(OPERATOR_TOKEN),
            json={
                "decision": "REJECT",
                "confirmation": decision_confirmation_challenge(
                    approval_id=approval["approval_id"], run_id=approval["run_id"], decision="REJECT"
                ),
            },
        )
        assert decided.status_code == 200, decided.text
        assert decided.json()["state"] == "CANCELLED"
        assert client.get(
            f"/v1/service/runs/{approval['run_id']}", headers=_headers(ALICE_TOKEN)
        ).json()["status"] == "CANCELLED"

def test_service_token_and_principal_identity_are_not_persisted(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        _preflight(client, ALICE_TOKEN, key="token-not-persisted-0001")
    raw = (tmp_path / "product.sqlite3").read_bytes()
    assert ALICE_TOKEN.encode() not in raw
    assert BOB_TOKEN.encode() not in raw
    assert MALLORY_TOKEN.encode() not in raw
    assert OPERATOR_TOKEN.encode() not in raw
    assert OTHER_OPERATOR_TOKEN.encode() not in raw
    assert b"alice-web" not in raw
    assert b"tenant-a" in raw
    assert b"alice" in raw
