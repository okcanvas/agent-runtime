from __future__ import annotations

import argparse
import base64
import json
import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import GatewayLifecycleEvent, GenericGatewayRunResult
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step018-acceptance-read-admin-key"
SUBMITTER_KEY = "step018-acceptance-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SUBMIT_HEADERS = {
    **ADMIN_HEADERS,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
}
RAW_REQUEST = "STEP018 acceptance raw request must remain encrypted outside SQLite"
IDEMPOTENCY_KEY = "step018-acceptance-idempotency-0001"


class AcceptanceGateway:
    def __init__(self) -> None:
        self.calls = 0
        self.received_request = None

    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        self.calls += 1
        self.received_request = request
        await lifecycle_sink(
            GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id})
        )
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        await lifecycle_sink(
            GatewayLifecycleEvent("model.completed", {"response_id": "resp_step018"})
        )
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "agent.completed", {"output_contract": definition.output_contract}
            )
        )
        return GenericGatewayRunResult(
            output=CodingAgentResult(
                status=AgentStatus.PASS,
                summary="Governed read-only acceptance completed.",
                findings=[],
                unverified=[],
            ),
            usage=UsageSummary(requests=1, input_tokens=9, output_tokens=4, total_tokens=13),
            trace_id="trace_step018",
            response_id="resp_step018",
            sdk_version="0.19.0",
        )


def _counts(database: Path) -> dict[str, int]:
    connection = sqlite3.connect(database)
    try:
        return {
            "tasks": int(connection.execute("SELECT COUNT(*) FROM task").fetchone()[0]),
            "runs": int(connection.execute("SELECT COUNT(*) FROM run").fetchone()[0]),
            "submissions": int(
                connection.execute("SELECT COUNT(*) FROM run_submission_preflight").fetchone()[0]
            ),
        }
    finally:
        connection.close()


def _wait_terminal(client: TestClient, run_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers=ADMIN_HEADERS)
        payload = response.json()
        if payload.get("status") in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return payload
        time.sleep(0.02)
    raise RuntimeError("Governed acceptance Run did not reach a terminal state")


def run_acceptance(output: Path) -> int:
    references_before = {
        item.reference_id: item.to_dict()
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    with AcceptanceWorkspace(step_id="STEP018", output=output) as workspace:
        product_db = workspace.database_dir / "product.sqlite3"
        payload_root = workspace.scratch_dir / "protected-payloads"
        gateway = AcceptanceGateway()
        app = create_app(
            project_root=ROOT,
            product_db=product_db,
            artifact_root=workspace.artifact_dir,
            evaluation_db=workspace.database_dir / "evaluation.sqlite3",
            admin_key=ADMIN_KEY,
            gateway=gateway,
            run_submitter_key=SUBMITTER_KEY,
            protected_payload_root=payload_root,
            protected_payload_key=PAYLOAD_KEY,
        )
        with TestClient(app) as client:
            read_only_denied = client.post(
                "/v1/run-submissions/preflight",
                headers=ADMIN_HEADERS,
                json={
                    "agent_definition_id": "coding-agent",
                    "input": RAW_REQUEST,
                    "model": "acceptance-model",
                    "idempotency_key": IDEMPOTENCY_KEY,
                },
            )
            preflight = client.post(
                "/v1/run-submissions/preflight",
                headers=SUBMIT_HEADERS,
                json={
                    "agent_definition_id": "coding-agent",
                    "input": RAW_REQUEST,
                    "model": "acceptance-model",
                    "idempotency_key": IDEMPOTENCY_KEY,
                },
            )
            first = preflight.json()
            first_payload = payload_root / f"{first['protected_payload_ref']}.json"
            payload_existed_before_confirm = first_payload.is_file()
            encrypted_bytes = first_payload.read_bytes()
            replay_preflight = client.post(
                "/v1/run-submissions/preflight",
                headers=SUBMIT_HEADERS,
                json={
                    "agent_definition_id": "coding-agent",
                    "input": RAW_REQUEST,
                    "model": "acceptance-model",
                    "idempotency_key": IDEMPOTENCY_KEY,
                },
            ).json()
            payload_count_after_replay = len(list(payload_root.glob("payload_*.json")))
            before_confirm = _counts(product_db)
            wrong_confirmation = client.post(
                f"/v1/run-submissions/{first['submission_id']}/confirm",
                headers=SUBMIT_HEADERS,
                json={"confirmation": first["confirmation_challenge"] + "x"},
            )
            after_wrong = _counts(product_db)
            confirmed_response = client.post(
                f"/v1/run-submissions/{first['submission_id']}/confirm",
                headers=SUBMIT_HEADERS,
                json={"confirmation": first["confirmation_challenge"]},
            )
            confirmed = confirmed_response.json()
            replay_confirmation = client.post(
                f"/v1/run-submissions/{first['submission_id']}/confirm",
                headers=SUBMIT_HEADERS,
                json={"confirmation": first["confirmation_challenge"]},
            ).json()
            terminal = _wait_terminal(client, confirmed["run_id"])
            events = client.get(
                f"/v1/runs/{confirmed['run_id']}/events", headers=ADMIN_HEADERS
            ).json()["events"]
            detail = client.get(
                f"/v1/run-submissions/{first['submission_id']}", headers=ADMIN_HEADERS
            ).json()
            direct = client.post(
                "/v1/runs",
                headers=ADMIN_HEADERS,
                json={"input": "must not execute", "confirm_live_call": True},
            )
            shell = client.get("/console")
            console_script = client.get("/console/assets/console.js")

            tamper_preflight = client.post(
                "/v1/run-submissions/preflight",
                headers=SUBMIT_HEADERS,
                json={
                    "agent_definition_id": "coding-agent",
                    "input": "tamper case",
                    "model": "acceptance-model",
                    "idempotency_key": "step018-acceptance-tamper-key",
                },
            ).json()
            tamper_path = payload_root / f"{tamper_preflight['protected_payload_ref']}.json"
            tamper_path.write_bytes(tamper_path.read_bytes() + b" ")
            tamper_denied = client.post(
                f"/v1/run-submissions/{tamper_preflight['submission_id']}/confirm",
                headers=SUBMIT_HEADERS,
                json={"confirmation": tamper_preflight["confirmation_challenge"]},
            )

        final_counts = _counts(product_db)
        connection = sqlite3.connect(product_db)
        try:
            task_payload_ref = connection.execute(
                "SELECT protected_payload_ref FROM task WHERE task_id = ?",
                (confirmed["task_id"],),
            ).fetchone()[0]
            ledger_state = connection.execute(
                "SELECT state FROM run_submission_preflight WHERE submission_id = ?",
                (first["submission_id"],),
            ).fetchone()[0]
        finally:
            connection.close()
        database_bytes = product_db.read_bytes()
        artifact_files = list(workspace.artifact_dir.rglob("final-output.json"))
        references_after = {
            item.reference_id: item.to_dict()
            for item in ReferenceCatalogService(ROOT).verify_all()
        }
        checks = {
            "separate_submitter_authority_required": read_only_denied.status_code == 403
            and read_only_denied.json().get("code") == "RUN_SUBMITTER_AUTHORITY_REQUIRED",
            "preflight_created": preflight.status_code == 201,
            "preflight_creates_no_task_or_run": before_confirm["tasks"] == 0
            and before_confirm["runs"] == 0,
            "protected_payload_persisted": first.get("protected_payload_persisted") is True
            and payload_existed_before_confirm,
            "raw_payload_not_in_sqlite": RAW_REQUEST.encode() not in database_bytes,
            "raw_payload_not_in_encrypted_file": RAW_REQUEST.encode() not in encrypted_bytes,
            "keys_not_persisted": SUBMITTER_KEY.encode() not in database_bytes
            and PAYLOAD_KEY.encode() not in database_bytes
            and PAYLOAD_KEY.encode() not in encrypted_bytes,
            "idempotent_preflight_reuses_submission": replay_preflight.get("submission_id")
            == first.get("submission_id")
            and replay_preflight.get("replayed") is True
            and payload_count_after_replay == 1,
            "wrong_confirmation_creates_nothing": wrong_confirmation.status_code == 409
            and after_wrong == before_confirm,
            "confirmed_submission_scheduled": confirmed_response.status_code == 202
            and confirmed.get("scheduled") is True
            and confirmed.get("replayed") is False,
            "exactly_one_task_and_run": final_counts["tasks"] == 1
            and final_counts["runs"] == 1,
            "task_bound_to_payload_reference": task_payload_ref == first.get("protected_payload_ref"),
            "confirmation_replay_same_task_run": replay_confirmation.get("task_id")
            == confirmed.get("task_id")
            and replay_confirmation.get("run_id") == confirmed.get("run_id")
            and replay_confirmation.get("scheduled") is False
            and replay_confirmation.get("replayed") is True,
            "gateway_invoked_once": gateway.calls == 1 and gateway.received_request == RAW_REQUEST,
            "run_completed": terminal.get("status") == "SUCCEEDED"
            and ledger_state == "EXECUTION_SUCCEEDED",
            "successful_payload_deleted": not first_payload.exists()
            and detail.get("payload_retention_state") == "DELETED",
            "governed_run_created_event": events[0].get("event_type") == "run.created"
            and events[0].get("source") == "operator"
            and events[0].get("payload", {}).get("submission_id") == first.get("submission_id"),
            "artifact_verified": len(artifact_files) == 1,
            "tampered_payload_rejected_without_second_run": tamper_denied.status_code == 409
            and tamper_denied.json().get("code") == "PROTECTED_PAYLOAD_INTEGRITY_FAILED"
            and final_counts["tasks"] == 1
            and final_counts["runs"] == 1,
            "submission_detail_safe": detail.get("input_sha256") == first.get("input_sha256")
            and "input" not in detail,
            "direct_run_api_disabled": direct.status_code == 403
            and direct.json().get("code") == "DIRECT_RUN_SUBMISSION_DISABLED",
            "console_remains_read_only": "Run Submission Boundary" in shell.text
            and 'method:"POST"' not in console_script.text,
            "references_unchanged": references_before == references_after,
        }
        payload: dict[str, object] = {
            "schema_version": "okcanvas-step018-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "submission_id": first.get("submission_id"),
            "task_id": confirmed.get("task_id"),
            "run_id": confirmed.get("run_id"),
            "protected_payload_ref": first.get("protected_payload_ref"),
            "counts": final_counts,
            "event_types": [item.get("event_type") for item in events],
            "gateway_calls": gateway.calls,
        }
        payload = workspace.finalize(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP018_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
