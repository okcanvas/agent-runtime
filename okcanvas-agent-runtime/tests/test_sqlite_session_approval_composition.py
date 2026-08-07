from __future__ import annotations

import base64
import json
import sqlite3
import sys
import types
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.approvals import decision_confirmation_challenge
from okcanvas_agent_runtime.application.approvals.testing import DeterministicToolApprovalGateway

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step046-test-admin-key"
SUBMITTER_KEY = "step046-test-submitter-key"
HEADERS = {
    "X-OKCanvas-Admin-Key": ADMIN_KEY,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
}
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_HISTORY_KEY = base64.urlsafe_b64encode(bytes(range(32, 64))).decode("ascii")


class FakeSQLiteSession:
    def __init__(self, session_id: str, db_path: str | Path) -> None:
        self.session_id = session_id
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_settings = None
        self.connection = sqlite3.connect(self.db_path, timeout=15, check_same_thread=False)
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS fake_session_item(
                session_id TEXT NOT NULL,
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                item_json TEXT NOT NULL
            )"""
        )
        self.connection.commit()

    async def get_items(self, limit: int | None = None):
        rows = self.connection.execute(
            "SELECT item_json FROM fake_session_item WHERE session_id=? ORDER BY sequence",
            (self.session_id,),
        ).fetchall()
        items = [json.loads(row[0]) for row in rows]
        return items[-limit:] if limit is not None else items

    async def add_items(self, items):
        self.connection.executemany(
            "INSERT INTO fake_session_item(session_id,item_json) VALUES(?,?)",
            [(self.session_id, json.dumps(item, sort_keys=True)) for item in items],
        )
        self.connection.commit()

    async def pop_item(self):
        row = self.connection.execute(
            "SELECT sequence,item_json FROM fake_session_item WHERE session_id=? ORDER BY sequence DESC LIMIT 1",
            (self.session_id,),
        ).fetchone()
        if row is None:
            return None
        self.connection.execute("DELETE FROM fake_session_item WHERE sequence=?", (row[0],))
        self.connection.commit()
        return json.loads(row[1])

    async def clear_session(self):
        self.connection.execute(
            "DELETE FROM fake_session_item WHERE session_id=?", (self.session_id,)
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()


def _app(tmp_path: Path, monkeypatch):
    module = types.ModuleType("agents")
    module.SQLiteSession = FakeSQLiteSession
    monkeypatch.setitem(sys.modules, "agents", module)
    return create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        evaluation_db=tmp_path / "evaluation.sqlite3",
        admin_key=ADMIN_KEY,
        run_submitter_key=SUBMITTER_KEY,
        protected_payload_root=tmp_path / "payloads",
        protected_payload_key=PAYLOAD_KEY,
        run_state_root=tmp_path / "run-states",
        session_root=tmp_path / "sessions",
        session_history_key=SESSION_HISTORY_KEY,
        tool_approval_gateway=DeterministicToolApprovalGateway(),
    )


def _preflight(client: TestClient, session_id: str, request: str, key: str) -> dict:
    response = client.post(
        "/v1/run-submissions/preflight",
        headers=HEADERS,
        json={
            "agent_definition_id": "session-approval-agent",
            "input": request,
            "model": "deterministic-step046-model",
            "idempotency_key": key,
            "session_id": session_id,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["execution_mode"] == "APPROVAL_INTERRUPTED"
    assert body["session_id"] == session_id
    return body


def _decide(client: TestClient, approval: dict, decision: str):
    return client.post(
        f"/v1/tool-approvals/{approval['approval_id']}/decision",
        headers=HEADERS,
        json={
            "decision": decision,
            "confirmation": decision_confirmation_challenge(
                approval_id=approval["approval_id"],
                run_id=approval["run_id"],
                decision=decision,
            ),
        },
    )


def test_session_approval_approve_and_reject_commit_once(tmp_path: Path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        created = client.post(
            "/v1/sessions",
            headers=HEADERS,
            json={"agent_definition_id": "session-approval-agent"},
        )
        assert created.status_code == 201, created.text
        session_id = created.json()["session_id"]

        first = _preflight(client, session_id, "First approved Session turn", "step046-unit-approve-0001")
        prepared = client.post(
            f"/v1/run-submissions/{first['submission_id']}/prepare-approval",
            headers=HEADERS,
        )
        assert prepared.status_code == 202, prepared.text
        approval = prepared.json()
        interrupted = client.get(f"/v1/sessions/{session_id}", headers=ADMIN_HEADERS).json()
        assert interrupted["active_run_id"] == approval["run_id"]
        assert interrupted["turn_count"] == 0
        assert interrupted["item_count"] == 2
        assert client.post(f"/v1/sessions/{session_id}/clear", headers=HEADERS).status_code == 409

        approved = _decide(client, approval, "APPROVE")
        assert approved.status_code == 200, approved.text
        after_approve = client.get(f"/v1/sessions/{session_id}", headers=ADMIN_HEADERS).json()
        assert after_approve["active_run_id"] is None
        assert (after_approve["turn_count"], after_approve["item_count"]) == (1, 4)

        replay = _decide(client, approval, "APPROVE")
        assert replay.status_code == 200, replay.text
        assert replay.json()["replayed"] is True
        assert client.get(f"/v1/sessions/{session_id}", headers=ADMIN_HEADERS).json()["item_count"] == 4

        second = _preflight(client, session_id, "Second rejected Session turn", "step046-unit-reject-0002")
        prepared2 = client.post(
            f"/v1/run-submissions/{second['submission_id']}/prepare-approval",
            headers=HEADERS,
        )
        assert prepared2.status_code == 202, prepared2.text
        approval2 = prepared2.json()
        rejected = _decide(client, approval2, "REJECT")
        assert rejected.status_code == 200, rejected.text
        after_reject = client.get(f"/v1/sessions/{session_id}", headers=ADMIN_HEADERS).json()
        assert (after_reject["turn_count"], after_reject["item_count"]) == (2, 8)
        assert after_reject["active_run_id"] is None
        replay2 = _decide(client, approval2, "REJECT")
        assert replay2.status_code == 200, replay2.text
        assert replay2.json()["replayed"] is True
        assert client.get(f"/v1/sessions/{session_id}", headers=ADMIN_HEADERS).json()["item_count"] == 8

        events = client.get(
            f"/v1/runs/{approval['run_id']}/events", headers=ADMIN_HEADERS
        ).json()["events"]
        event_types = [event["event_type"] for event in events]
        assert event_types.count("session.turn.started") == 1
        assert event_types.count("session.turn.interrupted") == 1
        assert event_types.count("session.turn.completed") == 1
        assert all("First approved Session turn" not in json.dumps(event) for event in events)
