from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.compatibility.source_contracts import component_asset_root, read_component_source
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.adapters.storage.protected_payload import generate_protected_payload_key
from okcanvas_agent_runtime.application.approvals import decision_confirmation_challenge
from okcanvas_agent_runtime.application.approvals.testing import DeterministicToolApprovalGateway

ROOT = Path(__file__).resolve().parents[1]
ADMIN = "step021-admin-key-123456"
SUBMITTER = "step021-submitter-key-123456"
READ_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN}
WRITE_HEADERS = {
    "X-OKCanvas-Admin-Key": ADMIN,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER,
}


def _app(tmp_path: Path):
    return create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        evaluation_db=tmp_path / "evaluation.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key=ADMIN,
        run_submitter_key=SUBMITTER,
        protected_payload_root=tmp_path / "protected-payloads",
        protected_payload_key=generate_protected_payload_key(),
        run_state_root=tmp_path / "run-states",
        tool_approval_gateway=DeterministicToolApprovalGateway(),
    )


def _pending(client: TestClient) -> dict:
    preflight = client.post(
        "/v1/run-submissions/preflight",
        headers=WRITE_HEADERS,
        json={
            "agent_definition_id": "local-text-metrics-agent",
            "input": "STEP021 approval inbox fixture",
            "model": "acceptance-model",
            "idempotency_key": "step021-inbox-idempotency-0001",
        },
    )
    assert preflight.status_code == 201, preflight.text
    response = client.post(
        f"/v1/run-submissions/{preflight.json()['submission_id']}/prepare-approval",
        headers=WRITE_HEADERS,
    )
    assert response.status_code == 202, response.text
    return response.json()


def test_read_only_approval_inbox_lists_safe_bounded_metadata(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    app = _app(tmp_path)
    with TestClient(app) as client:
        assert client.get("/v1/tool-approvals").status_code == 401
        approval = _pending(client)
        database_path = tmp_path / "product.sqlite3"
        before = hashlib.sha256(database_path.read_bytes()).hexdigest()

        response = client.get("/v1/tool-approvals?state=PENDING&limit=20", headers=READ_HEADERS)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["schema_version"] == "okcanvas-control-tool-approval-list-v1"
        assert body["total"] == 1
        assert body["limit"] == 20
        assert body["offset"] == 0
        item = body["approvals"][0]
        assert item["approval_id"] == approval["approval_id"]
        assert item["state"] == "PENDING"
        assert item["tool_name"] == "local_text_metrics"
        assert item["tool_execution_count"] == 0
        assert "run_state_ref" not in item
        assert "run_state_sha256" not in item
        assert "run_state_key_id" not in item
        assert "arguments_sha256" not in item
        assert "tool_call_id_sha256" not in item

        summary = client.get("/v1/operations/summary", headers=READ_HEADERS).json()
        assert summary["approvals"]["approval_total"] == 1
        assert summary["approvals"]["pending_total"] == 1
        assert summary["approvals"]["approval_states"]["PENDING"] == 1
        assert hashlib.sha256(database_path.read_bytes()).hexdigest() == before


def test_approval_inbox_filters_terminal_records_without_decision_capability(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    app = _app(tmp_path)
    with TestClient(app) as client:
        approval = _pending(client)
        decided = client.post(
            f"/v1/tool-approvals/{approval['approval_id']}/decision",
            headers=WRITE_HEADERS,
            json={"decision": "APPROVE", "confirmation": decision_confirmation_challenge(approval_id=approval["approval_id"], run_id=approval["run_id"], decision="APPROVE")},
        )
        assert decided.status_code == 200, decided.text

        succeeded = client.get("/v1/tool-approvals?state=SUCCEEDED", headers=READ_HEADERS).json()
        assert succeeded["total"] == 1
        assert succeeded["approvals"][0]["decision"] == "APPROVE"
        assert succeeded["approvals"][0]["tool_execution_count"] == 1
        pending = client.get("/v1/tool-approvals?state=PENDING", headers=READ_HEADERS).json()
        assert pending["total"] == 0
        assert client.get("/v1/tool-approvals?state=UNKNOWN", headers=READ_HEADERS).status_code == 422

        summary = client.get("/v1/operations/summary", headers=READ_HEADERS).json()
        assert summary["approvals"]["approval_total"] == 1
        assert summary["approvals"]["pending_total"] == 0
        assert summary["approvals"]["approval_states"]["SUCCEEDED"] == 1


def test_console_approval_inbox_remains_read_only() -> None:
    assets = component_asset_root(ROOT, "operations_console.assets")
    html = (assets / "index.html").read_text(encoding="utf-8")
    script = (assets / "console.js").read_text(encoding="utf-8")
    assert 'data-tab="approvals"' in html
    assert 'id="approvalsBody"' in html
    assert "승인·거절은 이 화면에서 수행하지 않습니다" in html
    assert 'api(`/v1/tool-approvals?limit=100' in script
    assert "/decision" not in script
    assert 'method:"POST"' not in script
    assert "X-OKCanvas-Run-Submitter-Key" not in script
