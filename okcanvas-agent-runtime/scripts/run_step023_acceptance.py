from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import threading
import time
from pathlib import Path
from typing import Any

import httpx
import uvicorn

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_clients.operator import (
    ApprovalOperatorConfig,
    ApprovalOperatorError,
    LocalApprovalOperatorClient,
)
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.adapters.storage.protected_payload import generate_protected_payload_key
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_runtime.application.approvals.testing import DeterministicToolApprovalGateway

ROOT = Path(__file__).resolve().parents[1]
ADMIN = "step023-acceptance-admin-key"
SUBMITTER = "step023-acceptance-submitter-key"
WRITE_HEADERS = {
    "X-OKCanvas-Admin-Key": ADMIN,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER,
}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _prepare(client: httpx.Client, label: str) -> dict[str, Any]:
    preflight = client.post(
        "/v1/run-submissions/preflight",
        headers=WRITE_HEADERS,
        json={
            "agent_definition_id": "local-text-metrics-agent",
            "input": f"STEP023 local approval operator {label}",
            "model": "acceptance-model",
            "idempotency_key": f"step023-{label}-idempotency-0001",
        },
    )
    if preflight.status_code != 201:
        raise RuntimeError(preflight.text)
    prepared = client.post(
        f"/v1/run-submissions/{preflight.json()['submission_id']}/prepare-approval",
        headers=WRITE_HEADERS,
    )
    if prepared.status_code != 202:
        raise RuntimeError(prepared.text)
    return prepared.json()


def _start_server(workspace: AcceptanceWorkspace) -> tuple[uvicorn.Server, threading.Thread, str]:
    app = create_app(
        project_root=ROOT,
        product_db=workspace.database_dir / "product.sqlite3",
        evaluation_db=workspace.database_dir / "evaluation.sqlite3",
        artifact_root=workspace.artifact_dir,
        admin_key=ADMIN,
        run_submitter_key=SUBMITTER,
        protected_payload_root=workspace.scratch_dir / "protected-payloads",
        protected_payload_key=generate_protected_payload_key(),
        run_state_root=workspace.scratch_dir / "run-states",
        tool_approval_gateway=DeterministicToolApprovalGateway(),
    )
    port = _free_port()
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        lifespan="on",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="step023-control-api", daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.02)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=5)
        raise RuntimeError("STEP023 loopback Control API did not start")
    return server, thread, f"http://127.0.0.1:{port}"


def run_acceptance(output: Path) -> int:
    os.environ.setdefault("OPENAI_API_KEY", "step023-not-a-real-api-key")
    before_results = ReferenceCatalogService(ROOT).verify_all()
    before = {item.reference_id: item.actual_tree_sha256 for item in before_results}

    with AcceptanceWorkspace(step_id="STEP023", output=output) as workspace:
        server, thread, base_url = _start_server(workspace)

        def stop_server() -> None:
            server.should_exit = True
            thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError("STEP023 loopback Control API did not stop")

        workspace.register_closer("loopback-control-api", stop_server)

        with httpx.Client(base_url=base_url, timeout=30) as setup_client:
            approve_record = _prepare(setup_client, "approve")
            reject_record = _prepare(setup_client, "reject")

        config = ApprovalOperatorConfig(
            base_url=base_url,
            admin_key=ADMIN,
            submitter_key=SUBMITTER,
            timeout_seconds=30,
        )
        wrong_confirmation_blocked = False
        wrong_confirmation_code = None
        with LocalApprovalOperatorClient(config) as operator:
            inbox = operator.list_approvals(state="PENDING", limit=20)
            approval_items = {
                item["approval_id"]: item for item in inbox.get("approvals", [])
            }
            approve_item = approval_items[approve_record["approval_id"]]
            reject_item = approval_items[reject_record["approval_id"]]
            try:
                operator.decide(
                    approval_id=approve_record["approval_id"],
                    decision="APPROVE",
                    confirmation="APPROVE wrong",
                )
            except ApprovalOperatorError as exc:
                wrong_confirmation_blocked = True
                wrong_confirmation_code = exc.code
            approve_result = operator.decide(
                approval_id=approve_record["approval_id"],
                decision="APPROVE",
                confirmation=approve_item["approve_confirmation"],
            )
            approve_replay = operator.decide(
                approval_id=approve_record["approval_id"],
                decision="APPROVE",
                confirmation=approve_item["approve_confirmation"],
            )
            reject_result = operator.decide(
                approval_id=reject_record["approval_id"],
                decision="REJECT",
                confirmation=reject_item["reject_confirmation"],
            )
            remaining = operator.list_approvals(state="PENDING", limit=20)

        product_db = workspace.database_dir / "product.sqlite3"
        database_bytes = product_db.read_bytes()
        output_text = json.dumps(
            {
                "inbox": inbox,
                "approve": approve_result,
                "reject": reject_result,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        forbidden_fields = {
            "run_state_ref",
            "run_state_sha256",
            "run_state_key_id",
            "arguments_sha256",
            "tool_call_id_sha256",
        }
        checks = {
            "loopback_http_used": base_url.startswith("http://127.0.0.1:"),
            "two_pending_approvals_listed": inbox.get("total") == 2,
            "safe_inbox_contract": all(
                not forbidden_fields.intersection(item)
                for item in inbox.get("approvals", [])
            ),
            "exact_confirmation_challenges_present": approve_item.get(
                "approve_confirmation"
            )
            == f"APPROVE {approve_record['approval_id']} {approve_record['run_id']}"
            and reject_item.get("reject_confirmation")
            == f"REJECT {reject_record['approval_id']} {reject_record['run_id']}",
            "wrong_confirmation_blocked": wrong_confirmation_blocked
            and wrong_confirmation_code == "TOOL_APPROVAL_CONFIRMATION_MISMATCH",
            "approve_succeeded": approve_result.get("state") == "SUCCEEDED",
            "approve_tool_executed_once": approve_result.get("tool_executed") is True
            and approve_result.get("approval", {}).get("tool_execution_count") == 1,
            "approve_replay_idempotent": approve_replay.get("replayed") is True
            and approve_replay.get("approval", {}).get("tool_execution_count") == 1,
            "reject_cancelled": reject_result.get("state") == "CANCELLED",
            "reject_tool_not_executed": reject_result.get("tool_executed") is False
            and reject_result.get("approval", {}).get("tool_execution_count") == 0,
            "no_pending_approvals_remain": remaining.get("total") == 0,
            "admin_key_not_persisted": ADMIN.encode() not in database_bytes,
            "submitter_key_not_persisted": SUBMITTER.encode() not in database_bytes,
            "keys_not_in_compact_output": ADMIN not in output_text
            and SUBMITTER not in output_text,
        }
        after_results = ReferenceCatalogService(ROOT).verify_all()
        after = {item.reference_id: item.actual_tree_sha256 for item in after_results}
        checks["references_unchanged"] = before == after and all(
            item.verified for item in after_results
        )
        payload: dict[str, Any] = {
            "schema_version": "okcanvas-step023-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "approval_total": inbox.get("total"),
            "approve_state": approve_result.get("state"),
            "reject_state": reject_result.get("state"),
            "product_db_sha256": hashlib.sha256(database_bytes).hexdigest(),
        }
        final = workspace.finalize(payload)
    print(json.dumps(final, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if final["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP023_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
