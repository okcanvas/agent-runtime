from __future__ import annotations

import argparse
import base64
import json
import os
import sqlite3
import sys
import types
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_runtime.domain.sessions import SessionBusyError
from okcanvas_agent_runtime.application.approvals import decision_confirmation_challenge
from okcanvas_agent_runtime.application.approvals.testing import DeterministicToolApprovalGateway

ADMIN_KEY = "step046-local-admin-key"
SUBMITTER_KEY = "step046-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_HISTORY_KEY = base64.urlsafe_b64encode(
    bytes((index + 67) % 256 for index in range(32))
).decode("ascii")
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SUBMIT_HEADERS = {**ADMIN_HEADERS, "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY}
APPROVE_REQUEST = "STEP046 approved SQLite Session Tool Turn sentinel"
REJECT_REQUEST = "STEP046 rejected SQLite Session Tool Turn sentinel"
HIDDEN_API_KEY = "step046-hidden-api-key"
MODEL = "deterministic-step046-model"


class CountingSQLiteSession:
    instances = 0
    closes = 0
    session_ids: list[str] = []

    def __init__(self, session_id: str, db_path: str | Path) -> None:
        type(self).instances += 1
        type(self).session_ids.append(session_id)
        self.session_id = session_id
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path, timeout=15, check_same_thread=False)
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS step046_session_item(
                session_id TEXT NOT NULL,
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                item_json TEXT NOT NULL
            )"""
        )
        self.connection.commit()
        self.closed = False

    async def get_items(self, limit: int | None = None):
        rows = self.connection.execute(
            "SELECT item_json FROM step046_session_item WHERE session_id=? ORDER BY sequence",
            (self.session_id,),
        ).fetchall()
        items = [json.loads(row[0]) for row in rows]
        return items[-limit:] if limit is not None else items

    async def add_items(self, items):
        self.connection.executemany(
            "INSERT INTO step046_session_item(session_id,item_json) VALUES(?,?)",
            [(self.session_id, json.dumps(item, ensure_ascii=False, sort_keys=True)) for item in items],
        )
        self.connection.commit()

    async def pop_item(self):
        row = self.connection.execute(
            "SELECT sequence,item_json FROM step046_session_item WHERE session_id=? ORDER BY sequence DESC LIMIT 1",
            (self.session_id,),
        ).fetchone()
        if row is None:
            return None
        self.connection.execute("DELETE FROM step046_session_item WHERE sequence=?", (row[0],))
        self.connection.commit()
        return json.loads(row[1])

    async def clear_session(self):
        self.connection.execute(
            "DELETE FROM step046_session_item WHERE session_id=?", (self.session_id,)
        )
        self.connection.commit()

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            type(self).closes += 1
            self.connection.close()


class CountingApprovalGateway(DeterministicToolApprovalGateway):
    def __init__(self) -> None:
        self.prepare_calls = 0
        self.resume_calls = 0

    async def prepare(self, **kwargs):
        self.prepare_calls += 1
        return await super().prepare(**kwargs)

    async def resume(self, **kwargs):
        self.resume_calls += 1
        return await super().resume(**kwargs)


def _install_fake_agents():
    previous = sys.modules.get("agents")
    module = types.ModuleType("agents")
    module.SQLiteSession = CountingSQLiteSession
    sys.modules["agents"] = module
    CountingSQLiteSession.instances = 0
    CountingSQLiteSession.closes = 0
    CountingSQLiteSession.session_ids = []
    return previous


def _restore_fake_agents(previous) -> None:
    if previous is None:
        sys.modules.pop("agents", None)
    else:
        sys.modules["agents"] = previous


def _preflight(client: TestClient, *, session_id: str, request: str, key: str) -> dict[str, Any]:
    response = client.post(
        "/v1/run-submissions/preflight",
        headers=SUBMIT_HEADERS,
        json={
            "agent_definition_id": "session-approval-agent",
            "input": request,
            "model": MODEL,
            "idempotency_key": key,
            "session_id": session_id,
        },
    )
    response.raise_for_status()
    return response.json()


def _prepare(client: TestClient, submission_id: str) -> dict[str, Any]:
    response = client.post(
        f"/v1/run-submissions/{submission_id}/prepare-approval",
        headers=SUBMIT_HEADERS,
    )
    response.raise_for_status()
    return response.json()


def _decide(client: TestClient, approval: dict[str, Any], decision: str):
    return client.post(
        f"/v1/tool-approvals/{approval['approval_id']}/decision",
        headers=SUBMIT_HEADERS,
        json={
            "decision": decision,
            "confirmation": decision_confirmation_challenge(
                approval_id=approval["approval_id"],
                run_id=approval["run_id"],
                decision=decision,
            ),
        },
    )


def _events(client: TestClient, run_id: str) -> list[dict[str, Any]]:
    response = client.get(f"/v1/runs/{run_id}/events", headers=ADMIN_HEADERS)
    response.raise_for_status()
    return response.json()["events"]


def _counts(product_db: Path, evaluation_db: Path) -> dict[str, int]:
    with sqlite3.connect(product_db) as conn:
        values = {
            "tasks": conn.execute("SELECT COUNT(*) FROM task").fetchone()[0],
            "runs": conn.execute("SELECT COUNT(*) FROM run").fetchone()[0],
            "submissions": conn.execute("SELECT COUNT(*) FROM run_submission_preflight").fetchone()[0],
            "invocations": conn.execute("SELECT COUNT(*) FROM agent_invocation").fetchone()[0],
            "events": conn.execute("SELECT COUNT(*) FROM run_event").fetchone()[0],
            "artifacts": conn.execute("SELECT COUNT(*) FROM artifact").fetchone()[0],
            "approvals": conn.execute("SELECT COUNT(*) FROM governed_tool_approval").fetchone()[0],
        }
    with sqlite3.connect(evaluation_db) as conn:
        values["evaluations"] = conn.execute("SELECT COUNT(*) FROM evaluation_result").fetchone()[0]
    return {key: int(value) for key, value in values.items()}


def _history_count(history_db: Path, session_id: str) -> int:
    with sqlite3.connect(history_db) as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM step046_session_item WHERE session_id=?", (session_id,)
            ).fetchone()[0]
        )


def run_acceptance(output: Path) -> int:
    os.environ.setdefault("OPENAI_API_KEY", HIDDEN_API_KEY)
    references_before = {
        item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()
    }
    previous_agents = _install_fake_agents()
    try:
        with AcceptanceWorkspace(step_id="STEP046", output=output) as workspace:
            product_db = workspace.database_dir / "product.sqlite3"
            evaluation_db = workspace.database_dir / "evaluation.sqlite3"
            payload_root = workspace.scratch_dir / "protected-payloads"
            session_root = workspace.scratch_dir / "sessions"
            gateway = CountingApprovalGateway()
            app = create_app(
                project_root=ROOT,
                product_db=product_db,
                artifact_root=workspace.artifact_dir,
                evaluation_db=evaluation_db,
                admin_key=ADMIN_KEY,
                run_submitter_key=SUBMITTER_KEY,
                protected_payload_root=payload_root,
                protected_payload_key=PAYLOAD_KEY,
                run_state_root=workspace.scratch_dir / "run-states",
                session_root=session_root,
                session_history_key=SESSION_HISTORY_KEY,
                tool_approval_gateway=gateway,
            )
            with TestClient(app) as client:
                unauthorized_session = client.post(
                    "/v1/sessions", json={"agent_definition_id": "session-approval-agent"}
                )
                created_response = client.post(
                    "/v1/sessions",
                    headers=SUBMIT_HEADERS,
                    json={"agent_definition_id": "session-approval-agent"},
                )
                created_response.raise_for_status()
                created = created_response.json()
                session_id = created["session_id"]
                definition = AgentDefinitionCatalog(ROOT).resolve("session-approval-agent")
                binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)

                approve_preflight = _preflight(
                    client,
                    session_id=session_id,
                    request=APPROVE_REQUEST,
                    key="step046-approve-idempotency-0001",
                )
                stored_approve_payload = app.state.protected_payload_store.read(
                    approve_preflight["protected_payload_ref"],
                    expected_file_sha256=approve_preflight["protected_payload_sha256"],
                    expected_byte_length=approve_preflight["protected_payload_byte_length"],
                )
                approve_pending = _prepare(client, approve_preflight["submission_id"])
                interrupted_approve = client.get(
                    f"/v1/sessions/{session_id}", headers=ADMIN_HEADERS
                ).json()
                clear_while_pending = client.post(
                    f"/v1/sessions/{session_id}/clear", headers=SUBMIT_HEADERS
                )
                busy_rejected = False
                try:
                    app.state.session_runtime.acquire_turn(
                        session_id=session_id,
                        run_id="run_step046_competing",
                        definition=definition,
                        runtime_binding_sha256=binding.runtime_binding_sha256,
                    )
                except SessionBusyError:
                    busy_rejected = True

                approve_response = _decide(client, approve_pending, "APPROVE")
                approve_response.raise_for_status()
                approve_result = approve_response.json()
                approve_replay_response = _decide(client, approve_pending, "APPROVE")
                approve_replay_response.raise_for_status()
                approve_replay = approve_replay_response.json()
                after_approve = client.get(
                    f"/v1/sessions/{session_id}", headers=ADMIN_HEADERS
                ).json()
                approve_events = _events(client, approve_pending["run_id"])
                approve_artifact_response = client.get(
                    f"/v1/runs/{approve_pending['run_id']}/artifact", headers=ADMIN_HEADERS
                )
                approve_evaluation_response = client.post(
                    f"/v1/runs/{approve_pending['run_id']}/evaluations",
                    headers=ADMIN_HEADERS,
                    json={"case_id": "sqlite-session-approval-v1"},
                )
                approve_evaluation_response.raise_for_status()
                approve_evaluation = approve_evaluation_response.json()

                reject_preflight = _preflight(
                    client,
                    session_id=session_id,
                    request=REJECT_REQUEST,
                    key="step046-reject-idempotency-0002",
                )
                stored_reject_payload = app.state.protected_payload_store.read(
                    reject_preflight["protected_payload_ref"],
                    expected_file_sha256=reject_preflight["protected_payload_sha256"],
                    expected_byte_length=reject_preflight["protected_payload_byte_length"],
                )
                reject_pending = _prepare(client, reject_preflight["submission_id"])
                interrupted_reject = client.get(
                    f"/v1/sessions/{session_id}", headers=ADMIN_HEADERS
                ).json()
                reject_response = _decide(client, reject_pending, "REJECT")
                reject_response.raise_for_status()
                reject_result = reject_response.json()
                reject_replay_response = _decide(client, reject_pending, "REJECT")
                reject_replay_response.raise_for_status()
                reject_replay = reject_replay_response.json()
                after_reject = client.get(
                    f"/v1/sessions/{session_id}", headers=ADMIN_HEADERS
                ).json()
                reject_events = _events(client, reject_pending["run_id"])
                approvals = client.get("/v1/tool-approvals", headers=ADMIN_HEADERS).json()
                approve_invocations = client.get(
                    f"/v1/runs/{approve_pending['run_id']}/invocations", headers=ADMIN_HEADERS
                ).json()["invocations"]
                reject_invocations = client.get(
                    f"/v1/runs/{reject_pending['run_id']}/invocations", headers=ADMIN_HEADERS
                ).json()["invocations"]

            final_counts = _counts(product_db, evaluation_db)
            history_count = _history_count(session_root / "history.sqlite3", session_id)
            protected_files = list(payload_root.glob("payload_*.json"))
            product_bytes = product_db.read_bytes()
            evaluation_bytes = evaluation_db.read_bytes()
            approve_types = [event["event_type"] for event in approve_events]
            reject_types = [event["event_type"] for event in reject_events]
            approve_session_events = [
                event for event in approve_events if event["event_type"].startswith("session.turn.")
            ]
            reject_session_events = [
                event for event in reject_events if event["event_type"].startswith("session.turn.")
            ]
            raw_values = [APPROVE_REQUEST, REJECT_REQUEST, HIDDEN_API_KEY]
            references_after = {
                item.reference_id: item.to_dict()
                for item in ReferenceCatalogService(ROOT).verify_all()
            }

            checks = {
                "session_api_auth_required": unauthorized_session.status_code == 401,
                "session_created_for_exact_agent_and_binding": (
                    created["agent_definition_id"] == "session-approval-agent"
                    and created["runtime_binding_sha256"] == binding.runtime_binding_sha256
                    and binding.execution_path == "sqlite-session-approval-execution-v1"
                ),
                "two_preflights_bound_same_session": (
                    approve_preflight["session_id"] == session_id
                    and reject_preflight["session_id"] == session_id
                    and approve_preflight["execution_mode"] == "APPROVAL_INTERRUPTED"
                    and reject_preflight["execution_mode"] == "APPROVAL_INTERRUPTED"
                ),
                "protected_payloads_bound_session_identity": (
                    stored_approve_payload.session_id == session_id
                    and stored_reject_payload.session_id == session_id
                ),
                "approval_prepare_and_resume_counts_exact": (
                    gateway.prepare_calls == 2 and gateway.resume_calls == 2
                ),
                "approve_interruption_holds_turn_lease": (
                    interrupted_approve["active_run_id"] == approve_pending["run_id"]
                    and interrupted_approve["turn_count"] == 0
                    and interrupted_approve["item_count"] == 2
                ),
                "clear_rejected_while_approval_pending": clear_while_pending.status_code == 409,
                "competing_turn_rejected_while_pending": busy_rejected,
                "approved_tool_executed_exactly_once": (
                    approve_result["tool_executed"] is True
                    and approve_result["approval"]["tool_execution_count"] == 1
                ),
                "approved_decision_replay_no_duplicate": (
                    approve_replay["replayed"] is True
                    and after_approve["turn_count"] == 1
                    and after_approve["item_count"] == 4
                ),
                "approved_turn_committed_and_lease_released": (
                    after_approve["active_run_id"] is None
                    and after_approve["turn_count"] == 1
                    and after_approve["item_count"] == 4
                ),
                "approved_artifact_verified": bool(
                    approve_artifact_response.status_code == 200
                    and approve_artifact_response.json()["sha256"]
                ),
                "approved_recorded_evaluation_passed": approve_evaluation.get("state") == "PASSED",
                "reject_interruption_extends_history_and_holds_lease": (
                    interrupted_reject["active_run_id"] == reject_pending["run_id"]
                    and interrupted_reject["turn_count"] == 1
                    and interrupted_reject["item_count"] == 6
                ),
                "rejected_tool_never_executed": (
                    reject_result["tool_executed"] is False
                    and reject_result["approval"]["tool_execution_count"] == 0
                    and reject_result["state"] == "CANCELLED"
                ),
                "rejected_decision_replay_no_duplicate": reject_replay["replayed"] is True,
                "rejected_turn_committed_and_lease_released": (
                    after_reject["active_run_id"] is None
                    and after_reject["turn_count"] == 2
                    and after_reject["item_count"] == 8
                    and history_count == 8
                ),
                "session_event_pairs_exact": (
                    [event["event_type"] for event in approve_session_events]
                    == ["session.turn.started", "session.turn.interrupted", "session.turn.completed"]
                    and [event["event_type"] for event in reject_session_events]
                    == ["session.turn.started", "session.turn.interrupted", "session.turn.completed"]
                ),
                "session_event_metadata_safe": all(
                    event["payload"].get("history_persisted_in_product_events") is False
                    for event in [*approve_session_events, *reject_session_events]
                ),
                "session_handles_closed": (
                    CountingSQLiteSession.instances == 10
                    and CountingSQLiteSession.closes == 10
                    and set(CountingSQLiteSession.session_ids) == {session_id}
                ),
                "root_invocations_succeeded_or_cancelled_without_workspace": (
                    len(approve_invocations) == 1
                    and approve_invocations[0]["state"] == "SUCCEEDED"
                    and approve_invocations[0]["workspace_access"] == "none"
                    and len(reject_invocations) == 1
                    and reject_invocations[0]["state"] == "CANCELLED"
                    and reject_invocations[0]["workspace_access"] == "none"
                ),
                "approval_inbox_exposes_session_identity": (
                    approvals["total"] == 2
                    and all(item["session_id"] == session_id for item in approvals["approvals"])
                ),
                "raw_history_not_copied_to_product_events": all(
                    value not in json.dumps([*approve_events, *reject_events], ensure_ascii=False)
                    for value in (APPROVE_REQUEST, REJECT_REQUEST)
                ),
                "raw_requests_and_api_key_not_in_product_or_evaluation_db": all(
                    value.encode() not in product_bytes and value.encode() not in evaluation_bytes
                    for value in raw_values
                ),
                "successful_payload_deleted_rejected_retained": (
                    len(protected_files) == 1
                    and reject_preflight["protected_payload_ref"] in protected_files[0].name
                    and approve_preflight["protected_payload_ref"] not in protected_files[0].name
                ),
                "final_product_counts_exact": final_counts == {
                    "tasks": 2,
                    "runs": 2,
                    "submissions": 2,
                    "invocations": 2,
                    "events": len(approve_events) + len(reject_events),
                    "artifacts": 1,
                    "approvals": 2,
                    "evaluations": 1,
                },
                "references_unchanged": references_before == references_after,
            }
            payload = {
                "schema_version": "okcanvas-step046-acceptance-v1",
                "state": "PASSED" if all(checks.values()) else "FAILED",
                "checks": checks,
                "session": {
                    "session_id": session_id,
                    "runtime_binding_sha256": binding.runtime_binding_sha256,
                    "after_prepare_approve": interrupted_approve,
                    "after_approve": after_approve,
                    "after_prepare_reject": interrupted_reject,
                    "after_reject": after_reject,
                    "history_item_count": history_count,
                },
                "gateway_counts": {
                    "prepare": gateway.prepare_calls,
                    "resume": gateway.resume_calls,
                    "session_instances": CountingSQLiteSession.instances,
                    "session_closes": CountingSQLiteSession.closes,
                },
                "approve": {
                    "approval_id": approve_pending["approval_id"],
                    "run_id": approve_pending["run_id"],
                    "tool_execution_count": approve_result["approval"]["tool_execution_count"],
                    "replayed": approve_replay["replayed"],
                    "event_count": len(approve_events),
                    "event_types": approve_types,
                    "evaluation_state": approve_evaluation.get("state"),
                },
                "reject": {
                    "approval_id": reject_pending["approval_id"],
                    "run_id": reject_pending["run_id"],
                    "tool_execution_count": reject_result["approval"]["tool_execution_count"],
                    "replayed": reject_replay["replayed"],
                    "event_count": len(reject_events),
                    "event_types": reject_types,
                },
                "final_counts": final_counts,
                "protected_payload_file_count": len(protected_files),
            }
            final = workspace.finalize(payload)
            print(json.dumps(final, ensure_ascii=False, indent=2, sort_keys=True))
            return 0 if final["state"] == "PASSED" else 1
    finally:
        _restore_fake_agents(previous_agents)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP046_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
