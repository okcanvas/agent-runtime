from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.adapters.storage.protected_payload import generate_protected_payload_key
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_runtime.application.approvals import decision_confirmation_challenge
from okcanvas_agent_runtime.application.approvals.testing import DeterministicToolApprovalGateway

ROOT = Path(__file__).resolve().parents[1]
ADMIN = "step021-acceptance-admin-key"
SUBMITTER = "step021-acceptance-submitter-key"
READ_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN}
WRITE_HEADERS = {
    "X-OKCanvas-Admin-Key": ADMIN,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER,
}


def _app(workspace: AcceptanceWorkspace):
    return create_app(
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


def _prepare(client: TestClient, label: str) -> dict:
    preflight = client.post(
        "/v1/run-submissions/preflight",
        headers=WRITE_HEADERS,
        json={
            "agent_definition_id": "local-text-metrics-agent",
            "input": f"STEP021 approval inbox {label}",
            "model": "acceptance-model",
            "idempotency_key": f"step021-{label}-idempotency-0001",
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


def run_acceptance(output: Path) -> int:
    os.environ.setdefault("OPENAI_API_KEY", "step021-not-a-real-api-key")
    before = {
        item.reference_id: item.actual_tree_sha256
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    with AcceptanceWorkspace(step_id="STEP021", output=output) as workspace:
        app = _app(workspace)
        with TestClient(app) as client:
            pending = _prepare(client, "pending")
            completed = _prepare(client, "completed")
            decision = client.post(
                f"/v1/tool-approvals/{completed['approval_id']}/decision",
                headers=WRITE_HEADERS,
                json={"decision": "APPROVE", "confirmation": decision_confirmation_challenge(approval_id=completed["approval_id"], run_id=completed["run_id"], decision="APPROVE")},
            )
            product_db = workspace.database_dir / "product.sqlite3"
            database_sha_before_reads = hashlib.sha256(product_db.read_bytes()).hexdigest()
            unauthorized = client.get("/v1/tool-approvals")
            all_response = client.get("/v1/tool-approvals?limit=100", headers=READ_HEADERS)
            pending_response = client.get(
                "/v1/tool-approvals?state=PENDING&limit=100", headers=READ_HEADERS
            )
            succeeded_response = client.get(
                "/v1/tool-approvals?state=SUCCEEDED&limit=100", headers=READ_HEADERS
            )
            summary_response = client.get("/v1/operations/summary", headers=READ_HEADERS)
            console_response = client.get("/console")
            script_response = client.get("/console/assets/console.js")
            database_sha_after_reads = hashlib.sha256(product_db.read_bytes()).hexdigest()

        all_body = all_response.json()
        pending_body = pending_response.json()
        succeeded_body = succeeded_response.json()
        summary = summary_response.json()
        safe_items = all_body.get("approvals", [])
        forbidden_fields = {
            "run_state_ref",
            "run_state_sha256",
            "run_state_key_id",
            "arguments_sha256",
            "tool_call_id_sha256",
        }
        script = script_response.text
        checks = {
            "authentication_required": unauthorized.status_code == 401,
            "two_approval_records_listed": all_response.status_code == 200
            and all_body.get("total") == 2,
            "pending_filter_exact": pending_response.status_code == 200
            and pending_body.get("total") == 1
            and pending_body["approvals"][0]["approval_id"] == pending["approval_id"],
            "succeeded_filter_exact": succeeded_response.status_code == 200
            and succeeded_body.get("total") == 1
            and succeeded_body["approvals"][0]["approval_id"] == completed["approval_id"],
            "summary_pending_count": summary_response.status_code == 200
            and summary["approvals"]["approval_total"] == 2
            and summary["approvals"]["pending_total"] == 1,
            "safe_inbox_contract": bool(safe_items)
            and all(not forbidden_fields.intersection(item) for item in safe_items),
            "reads_do_not_mutate_product_db": database_sha_before_reads
            == database_sha_after_reads,
            "console_has_approval_inbox": console_response.status_code == 200
            and 'data-tab="approvals"' in console_response.text
            and 'id="approvalsBody"' in console_response.text,
            "console_has_no_decision_control": "/decision" not in script
            and 'method:"POST"' not in script
            and "X-OKCanvas-Run-Submitter-Key" not in script,
            "completed_tool_executed_once": decision.status_code == 200
            and decision.json()["approval"]["tool_execution_count"] == 1,
        }
        after_results = ReferenceCatalogService(ROOT).verify_all()
        after = {item.reference_id: item.actual_tree_sha256 for item in after_results}
        checks["references_unchanged"] = before == after and all(
            item.verified for item in after_results
        )
        payload = {
            "schema_version": "okcanvas-step021-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "pending_approval_id": pending["approval_id"],
            "completed_approval_id": completed["approval_id"],
            "approval_total": all_body.get("total"),
            "pending_total": summary.get("approvals", {}).get("pending_total"),
        }
        final = workspace.finalize(payload)
    print(json.dumps(final, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if final["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP021_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
