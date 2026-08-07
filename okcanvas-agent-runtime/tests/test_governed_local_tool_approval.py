from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.adapters.storage.protected_payload import generate_protected_payload_key
from okcanvas_agent_runtime.application.approvals import decision_confirmation_challenge
from okcanvas_agent_runtime.application.approvals.testing import DeterministicToolApprovalGateway

ROOT = Path(__file__).resolve().parents[1]
ADMIN = "A" * 24
SUBMITTER = "B" * 24
HEADERS = {"X-OKCanvas-Admin-Key": ADMIN, "X-OKCanvas-Run-Submitter-Key": SUBMITTER}


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


def _preflight(client: TestClient, suffix: str):
    response = client.post(
        "/v1/run-submissions/preflight",
        headers=HEADERS,
        json={
            "agent_definition_id": "local-text-metrics-agent",
            "input": f"approved metrics payload {suffix}",
            "model": "acceptance-model",
            "idempotency_key": f"step020-local-tool-{suffix}-0001",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["execution_mode"] == "APPROVAL_INTERRUPTED"
    assert payload["protected_payload_persisted"] is True
    return payload


def test_approve_persists_interruption_and_executes_tool_once(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    app = _app(tmp_path)
    with TestClient(app) as client:
        submission = _preflight(client, "approve")
        prepared = client.post(
            f"/v1/run-submissions/{submission['submission_id']}/prepare-approval",
            headers=HEADERS,
        )
        assert prepared.status_code == 202, prepared.text
        approval = prepared.json()
        assert approval["state"] == "PENDING"
        assert approval["tool_name"] == "local_text_metrics"
        run = client.get(f"/v1/runs/{approval['run_id']}", headers={"X-OKCanvas-Admin-Key": ADMIN}).json()
        task = client.get(f"/v1/tasks/{approval['task_id']}", headers={"X-OKCanvas-Admin-Key": ADMIN}).json()
        assert run["status"] == "INTERRUPTED"
        assert task["status"] == "WAITING_APPROVAL"
        raw_db = (tmp_path / "product.sqlite3").read_bytes()
        assert b"approved metrics payload approve" not in raw_db
        state_file = tmp_path / "run-states" / f"{approval['run_state_ref']}.json"
        assert state_file.is_file()
        assert b"approved metrics payload approve" not in state_file.read_bytes()

        resumed = client.post(
            f"/v1/tool-approvals/{approval['approval_id']}/decision",
            headers=HEADERS,
            json={"decision": "APPROVE", "confirmation": decision_confirmation_challenge(approval_id=approval["approval_id"], run_id=approval["run_id"], decision="APPROVE")},
        )
        assert resumed.status_code == 200, resumed.text
        body = resumed.json()
        assert body["state"] == "SUCCEEDED"
        assert body["tool_executed"] is True
        assert body["approval"]["tool_execution_count"] == 1
        assert body["artifact_id"]
        assert not state_file.exists()
        repeated = client.post(
            f"/v1/tool-approvals/{approval['approval_id']}/decision",
            headers=HEADERS,
            json={"decision": "APPROVE", "confirmation": decision_confirmation_challenge(approval_id=approval["approval_id"], run_id=approval["run_id"], decision="APPROVE")},
        )
        assert repeated.status_code == 200
        assert repeated.json()["replayed"] is True
        assert repeated.json()["approval"]["tool_execution_count"] == 1
        events = client.get(f"/v1/runs/{approval['run_id']}/events", headers={"X-OKCanvas-Admin-Key": ADMIN}).json()["events"]
        types = [item["event_type"] for item in events]
        assert "tool.approval.requested" in types
        assert "run.interrupted" in types
        assert "tool.approval.decided" in types
        assert "run.resumed" in types
        assert types.count("tool.started") == 1
        assert types.count("tool.completed") == 1


def test_reject_resumes_sdk_without_tool_execution(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    app = _app(tmp_path)
    with TestClient(app) as client:
        submission = _preflight(client, "reject")
        approval = client.post(
            f"/v1/run-submissions/{submission['submission_id']}/prepare-approval",
            headers=HEADERS,
        ).json()
        result = client.post(
            f"/v1/tool-approvals/{approval['approval_id']}/decision",
            headers=HEADERS,
            json={"decision": "REJECT", "confirmation": decision_confirmation_challenge(approval_id=approval["approval_id"], run_id=approval["run_id"], decision="REJECT")},
        )
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["state"] == "CANCELLED"
        assert body["tool_executed"] is False
        assert body["approval"]["state"] == "REJECTED"
        assert body["approval"]["tool_execution_count"] == 0
        events = client.get(f"/v1/runs/{approval['run_id']}/events", headers={"X-OKCanvas-Admin-Key": ADMIN}).json()["events"]
        types = [item["event_type"] for item in events]
        assert "tool.started" not in types
        assert "tool.completed" not in types
        assert "run.cancelled" in types


def test_tampered_encrypted_runstate_fails_closed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    app = _app(tmp_path)
    with TestClient(app) as client:
        submission = _preflight(client, "tamper")
        approval = client.post(
            f"/v1/run-submissions/{submission['submission_id']}/prepare-approval",
            headers=HEADERS,
        ).json()
        state_file = tmp_path / "run-states" / f"{approval['run_state_ref']}.json"
        state_file.write_bytes(state_file.read_bytes() + b"tamper")
        response = client.post(
            f"/v1/tool-approvals/{approval['approval_id']}/decision",
            headers=HEADERS,
            json={"decision": "APPROVE", "confirmation": decision_confirmation_challenge(approval_id=approval["approval_id"], run_id=approval["run_id"], decision="APPROVE")},
        )
        assert response.status_code == 409
        record = client.get(
            f"/v1/tool-approvals/{approval['approval_id']}",
            headers={"X-OKCanvas-Admin-Key": ADMIN},
        ).json()
        assert record["state"] == "FAILED"
        assert record["tool_execution_count"] == 0
        run = client.get(
            f"/v1/runs/{approval['run_id']}",
            headers={"X-OKCanvas-Admin-Key": ADMIN},
        ).json()
        assert run["status"] == "FAILED"
        assert state_file.exists()  # preserved as failure evidence


def test_opposite_terminal_decision_is_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    app = _app(tmp_path)
    with TestClient(app) as client:
        submission = _preflight(client, "opposite")
        approval = client.post(
            f"/v1/run-submissions/{submission['submission_id']}/prepare-approval",
            headers=HEADERS,
        ).json()
        approved = client.post(
            f"/v1/tool-approvals/{approval['approval_id']}/decision",
            headers=HEADERS,
            json={"decision": "APPROVE", "confirmation": decision_confirmation_challenge(approval_id=approval["approval_id"], run_id=approval["run_id"], decision="APPROVE")},
        )
        assert approved.status_code == 200
        opposite = client.post(
            f"/v1/tool-approvals/{approval['approval_id']}/decision",
            headers=HEADERS,
            json={"decision": "REJECT", "confirmation": decision_confirmation_challenge(approval_id=approval["approval_id"], run_id=approval["run_id"], decision="REJECT")},
        )
        assert opposite.status_code == 409


def test_wrong_resume_model_leaves_pending_approval_resumable(tmp_path: Path, monkeypatch) -> None:
    import asyncio

    import pytest

    from okcanvas_agent_runtime.core.config import RuntimeSettings
    from okcanvas_agent_runtime.application.approvals import ToolApprovalIntegrityError

    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    app = _app(tmp_path)
    with TestClient(app) as client:
        submission = _preflight(client, "wrong-model")
        approval = client.post(
            f"/v1/run-submissions/{submission['submission_id']}/prepare-approval",
            headers=HEADERS,
        ).json()
        with pytest.raises(ToolApprovalIntegrityError):
            asyncio.run(
                app.state.tool_approval_service.decide(
                    approval_id=approval["approval_id"],
                    decision=__import__(
                        "okcanvas_agent_runtime.application.approvals",
                        fromlist=["ToolApprovalDecision"],
                    ).ToolApprovalDecision.APPROVE,
                    settings=RuntimeSettings(model="wrong-model", api_key="not-a-real-key"),
                )
            )
        persisted = client.get(
            f"/v1/tool-approvals/{approval['approval_id']}",
            headers={"X-OKCanvas-Admin-Key": ADMIN},
        ).json()
        assert persisted["state"] == "PENDING"
        run = client.get(
            f"/v1/runs/{approval['run_id']}",
            headers={"X-OKCanvas-Admin-Key": ADMIN},
        ).json()
        task = client.get(
            f"/v1/tasks/{approval['task_id']}",
            headers={"X-OKCanvas-Admin-Key": ADMIN},
        ).json()
        assert run["status"] == "INTERRUPTED"
        assert task["status"] == "WAITING_APPROVAL"


def test_inconsistent_product_state_rolls_back_decision_claim(tmp_path: Path, monkeypatch) -> None:
    import sqlite3

    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    app = _app(tmp_path)
    with TestClient(app) as client:
        submission = _preflight(client, "state-drift")
        approval = client.post(
            f"/v1/run-submissions/{submission['submission_id']}/prepare-approval",
            headers=HEADERS,
        ).json()
        with sqlite3.connect(tmp_path / "product.sqlite3") as connection:
            connection.execute(
                "UPDATE run SET status='CREATED' WHERE run_id=?",
                (approval["run_id"],),
            )
        response = client.post(
            f"/v1/tool-approvals/{approval['approval_id']}/decision",
            headers=HEADERS,
            json={"decision": "APPROVE", "confirmation": decision_confirmation_challenge(approval_id=approval["approval_id"], run_id=approval["run_id"], decision="APPROVE")},
        )
        assert response.status_code == 409
        persisted = client.get(
            f"/v1/tool-approvals/{approval['approval_id']}",
            headers={"X-OKCanvas-Admin-Key": ADMIN},
        ).json()
        assert persisted["state"] == "PENDING"
        assert persisted["decision"] is None


def test_wrong_decision_confirmation_preserves_pending_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    app = _app(tmp_path)
    with TestClient(app) as client:
        submission = _preflight(client, "wrong-confirmation")
        approval = client.post(
            f"/v1/run-submissions/{submission['submission_id']}/prepare-approval",
            headers=HEADERS,
        ).json()
        response = client.post(
            f"/v1/tool-approvals/{approval['approval_id']}/decision",
            headers=HEADERS,
            json={"decision": "APPROVE", "confirmation": "APPROVE wrong"},
        )
        assert response.status_code == 409
        assert response.json()["code"] == "TOOL_APPROVAL_CONFIRMATION_MISMATCH"
        persisted = client.get(
            f"/v1/tool-approvals/{approval['approval_id']}",
            headers={"X-OKCanvas-Admin-Key": ADMIN},
        ).json()
        assert persisted["state"] == "PENDING"
        assert persisted["decision"] is None
        assert persisted["tool_execution_count"] == 0
