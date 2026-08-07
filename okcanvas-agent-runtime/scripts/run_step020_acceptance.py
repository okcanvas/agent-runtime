from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_runtime.application.approvals import decision_confirmation_challenge
from okcanvas_agent_runtime.application.approvals.testing import DeterministicToolApprovalGateway

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step020-acceptance-admin-key"
SUBMITTER_KEY = "step020-acceptance-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
HEADERS = {
    "X-OKCanvas-Admin-Key": ADMIN_KEY,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
}


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _redact(text: str) -> str:
    redacted = text
    for secret in (os.environ.get("OPENAI_API_KEY"), ADMIN_KEY, SUBMITTER_KEY, PAYLOAD_KEY):
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def _write_child_process_evidence(branch: Path, action: str, process: subprocess.CompletedProcess[str]) -> None:
    _write(
        branch / f"{action}-child-process.json",
        {
            "action": action,
            "return_code": process.returncode,
            "stdout": _redact(process.stdout),
            "stderr": _redact(process.stderr),
        },
    )


def _require_child_result(branch: Path, filename: str, process: subprocess.CompletedProcess[str], action: str) -> dict:
    _write_child_process_evidence(branch, action, process)
    result_path = branch / filename
    if not result_path.is_file():
        raise RuntimeError(
            f"STEP020 {action} child exited {process.returncode} without {filename}; "
            f"see {branch / f'{action}-child-process.json'}"
        )
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    if payload.get("state") == "FAILED":
        raise RuntimeError(
            f"STEP020 {action} child failed: {payload.get('error_type')}: {payload.get('error')}; "
            f"see {branch / f'{action}-child-process.json'}"
        )
    if process.returncode != 0:
        raise RuntimeError(
            f"STEP020 {action} child exited {process.returncode}; "
            f"see {branch / f'{action}-child-process.json'}"
        )
    return payload


def _app(branch: Path, *, live: bool):
    return create_app(
        project_root=ROOT,
        product_db=branch / "product.sqlite3",
        evaluation_db=branch / "evaluation.sqlite3",
        artifact_root=branch / "artifacts",
        admin_key=ADMIN_KEY,
        run_submitter_key=SUBMITTER_KEY,
        protected_payload_root=branch / "protected-payloads",
        protected_payload_key=PAYLOAD_KEY,
        run_state_root=branch / "run-states",
        tool_approval_gateway=None if live else DeterministicToolApprovalGateway(),
    )


def child_prepare(branch: Path, label: str, *, live: bool) -> int:
    try:
        if not live:
            os.environ["OPENAI_API_KEY"] = "step020-not-a-real-api-key"
        model = os.environ.get("OKCANVAS_AGENT_MODEL", "acceptance-model") if live else "acceptance-model"
        with TestClient(_app(branch, live=live)) as client:
            preflight = client.post(
                "/v1/run-submissions/preflight",
                headers=HEADERS,
                json={
                    "agent_definition_id": "local-text-metrics-agent",
                    "input": f"STEP020 protected local Tool payload {label}",
                    "model": model,
                    "idempotency_key": f"step020-{label}-idempotency-0001",
                },
            )
            if preflight.status_code != 201:
                _write(branch / "prepare-result.json", {"pid": os.getpid(), "state": "FAILED", "error_type": "PreflightHTTPError", "error": _redact(preflight.text)})
                return 1
            submission = preflight.json()
            response = client.post(
                f"/v1/run-submissions/{submission['submission_id']}/prepare-approval",
                headers=HEADERS,
            )
            payload = {
                "pid": os.getpid(),
                "state": "SUCCEEDED" if response.status_code == 202 else "FAILED",
                "status_code": response.status_code,
                "submission": submission,
                "approval": response.json(),
            }
            if response.status_code != 202:
                payload["error_type"] = "PrepareApprovalHTTPError"
                payload["error"] = _redact(response.text)
            _write(branch / "prepare-result.json", payload)
            return 0 if response.status_code == 202 else 1
    except Exception as exc:
        _write(
            branch / "prepare-result.json",
            {
                "pid": os.getpid(),
                "state": "FAILED",
                "error_type": type(exc).__name__,
                "error": _redact(str(exc)),
                "traceback": _redact(traceback.format_exc()),
            },
        )
        return 1


def child_decide(branch: Path, decision: str, *, live: bool) -> int:
    try:
        if not live:
            os.environ["OPENAI_API_KEY"] = "step020-not-a-real-api-key"
        prepared = json.loads((branch / "prepare-result.json").read_text(encoding="utf-8"))
        approval_id = prepared["approval"]["approval_id"]
        with TestClient(_app(branch, live=live)) as client:
            response = client.post(
                f"/v1/tool-approvals/{approval_id}/decision",
                headers=HEADERS,
                json={"decision": decision, "confirmation": decision_confirmation_challenge(approval_id=approval_id, run_id=prepared["approval"]["run_id"], decision=decision)},
            )
            repeated = client.post(
                f"/v1/tool-approvals/{approval_id}/decision",
                headers=HEADERS,
                json={"decision": decision, "confirmation": decision_confirmation_challenge(approval_id=approval_id, run_id=prepared["approval"]["run_id"], decision=decision)},
            )
            events = client.get(
                f"/v1/runs/{prepared['approval']['run_id']}/events",
                headers={"X-OKCanvas-Admin-Key": ADMIN_KEY},
            )
            payload = {
                "pid": os.getpid(),
                "state": "SUCCEEDED" if response.status_code == 200 and repeated.status_code == 200 else "FAILED",
                "status_code": response.status_code,
                "result": response.json(),
                "repeat_status_code": repeated.status_code,
                "repeated": repeated.json(),
                "events": events.json(),
            }
            if payload["state"] == "FAILED":
                payload["error_type"] = "DecisionHTTPError"
                payload["error"] = _redact(response.text)
            _write(branch / "decision-result.json", payload)
            return 0 if payload["state"] == "SUCCEEDED" else 1
    except Exception as exc:
        _write(
            branch / "decision-result.json",
            {
                "pid": os.getpid(),
                "state": "FAILED",
                "error_type": type(exc).__name__,
                "error": _redact(str(exc)),
                "traceback": _redact(traceback.format_exc()),
            },
        )
        return 1


def _run_child(branch: Path, action: str, value: str, *, live: bool) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--child-action", action, "--branch", str(branch), "--value", value, *(["--live"] if live else [])],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _branch(workspace: AcceptanceWorkspace, label: str, decision: str, *, live: bool) -> dict:
    branch = workspace.scratch_dir / label
    branch.mkdir(parents=True)
    prepare_process = _run_child(branch, "prepare", label, live=live)
    prepared = _require_child_result(branch, "prepare-result.json", prepare_process, "prepare")
    approval = prepared["approval"]
    raw = f"STEP020 protected local Tool payload {label}".encode()
    database = (branch / "product.sqlite3").read_bytes()
    state_path = branch / "run-states" / f"{approval['run_state_ref']}.json"
    before = {
        "prepare_process_ok": prepare_process.returncode == 0,
        "waiting_approval": approval["state"] == "PENDING",
        "runstate_exists_before_decision": state_path.is_file(),
        "raw_payload_not_in_database": raw not in database,
        "raw_payload_not_in_runstate": state_path.is_file() and raw not in state_path.read_bytes(),
    }
    decision_process = _run_child(branch, "decide", decision, live=live)
    decided = _require_child_result(branch, "decision-result.json", decision_process, "decision")
    result = decided["result"]
    events = decided["events"]["events"]
    types = [item["event_type"] for item in events]
    payload_files = list((branch / "protected-payloads").glob("*.json"))
    checks = {
        **before,
        "decision_process_ok": decision_process.returncode == 0,
        "process_restart_proven": prepared["pid"] != decided["pid"],
        "runstate_deleted_after_decision": not state_path.exists(),
        "duplicate_decision_replayed": decided["repeated"].get("replayed") is True,
        "approval_requested_event": "tool.approval.requested" in types,
        "run_interrupted_event": "run.interrupted" in types,
        "approval_decided_event": "tool.approval.decided" in types,
        "run_resumed_event": "run.resumed" in types,
    }
    if decision == "APPROVE":
        checks.update({
            "approved_succeeded": result["state"] == "SUCCEEDED",
            "tool_executed_exactly_once": result["approval"]["tool_execution_count"] == 1 and types.count("tool.started") == 1 and types.count("tool.completed") == 1,
            "artifact_created": bool(result.get("artifact_id")),
            "successful_payload_deleted": len(payload_files) == 0,
        })
    else:
        checks.update({
            "rejected_cancelled": result["state"] == "CANCELLED",
            "tool_not_executed": result["approval"]["tool_execution_count"] == 0 and "tool.started" not in types and "tool.completed" not in types,
            "rejected_payload_retained": len(payload_files) == 1,
        })
    return {
        "label": label,
        "decision": decision,
        "prepare_pid": prepared["pid"],
        "decision_pid": decided["pid"],
        "approval_id": approval["approval_id"],
        "run_id": approval["run_id"],
        "checks": checks,
        "event_types": types,
        "state": "PASSED" if all(checks.values()) else "FAILED",
    }


def run_acceptance(output: Path, *, live: bool = False) -> int:
    before = {item.reference_id: item.actual_tree_sha256 for item in ReferenceCatalogService(ROOT).verify_all()}
    with AcceptanceWorkspace(step_id="STEP020", output=output) as workspace:
        approve = _branch(workspace, "approve", "APPROVE", live=live)
        reject = _branch(workspace, "reject", "REJECT", live=live)
        after_results = ReferenceCatalogService(ROOT).verify_all()
        after = {item.reference_id: item.actual_tree_sha256 for item in after_results}
        checks = {
            "approve_branch_passed": approve["state"] == "PASSED",
            "reject_branch_passed": reject["state"] == "PASSED",
            "references_unchanged": before == after and all(item.verified for item in after_results),
        }
        payload = {
            "schema_version": "okcanvas-step020-live-acceptance-v1" if live else "okcanvas-step020-acceptance-v1",
            "live_sdk": live,
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "approve": approve,
            "reject": reject,
        }
        final = workspace.finalize(payload)
    print(json.dumps(final, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if final["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "evidence" / "STEP020_ACCEPTANCE.json")
    parser.add_argument("--child-action", choices=("prepare", "decide"))
    parser.add_argument("--branch", type=Path)
    parser.add_argument("--value")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if args.child_action == "prepare":
        return child_prepare(args.branch, args.value, live=args.live)
    if args.child_action == "decide":
        return child_decide(args.branch, args.value, live=args.live)
    return run_acceptance(args.output, live=args.live)


if __name__ == "__main__":
    raise SystemExit(main())
