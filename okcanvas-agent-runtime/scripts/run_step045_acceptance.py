from __future__ import annotations

import argparse
import base64
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.compatibility.source_contracts import read_component_source
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import GatewayLifecycleEvent, GenericGatewayRunResult
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_runtime.application.scenarios import WalkingSkeletonScenarioCatalog

ADMIN_KEY = "step045-local-admin-key"
SUBMITTER_KEY = "step045-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SUBMIT_HEADERS = {**ADMIN_HEADERS, "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY}
RAW_REQUEST = "STEP045 integrated tool-free runner sentinel"


class ToolFreeMatrixGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        self.calls += 1
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        await lifecycle_sink(GatewayLifecycleEvent("model.completed", {"response_id": "resp-step045"}))
        await lifecycle_sink(GatewayLifecycleEvent("agent.completed", {"agent_id": definition.agent_id}))
        return GenericGatewayRunResult(
            output=CodingAgentResult(
                status=AgentStatus.PASS,
                summary="Integrated walking skeleton tool-free path completed.",
                findings=[],
                unverified=[],
            ),
            usage=UsageSummary(requests=1, input_tokens=9, output_tokens=4, total_tokens=13),
            trace_id="trace-step045-tool-free",
            response_id="resp-step045",
            sdk_version="0.19.0-test-double",
        )


def _wait(client: TestClient, run_id: str) -> dict[str, object]:
    for _ in range(200):
        response = client.get(f"/v1/runs/{run_id}", headers=ADMIN_HEADERS)
        response.raise_for_status()
        body = response.json()
        if body["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return body
        time.sleep(0.02)
    raise RuntimeError("Tool-free matrix Run did not terminalize")


def _execute_tool_free(client: TestClient) -> dict[str, object]:
    preflight = client.post(
        "/v1/run-submissions/preflight",
        headers=SUBMIT_HEADERS,
        json={
            "agent_definition_id": "coding-agent",
            "input": RAW_REQUEST,
            "idempotency_key": "step045-tool-free-idempotency-0001",
            "model": "step045-deterministic-model",
        },
    )
    preflight.raise_for_status()
    prepared = preflight.json()
    confirmed_response = client.post(
        f"/v1/run-submissions/{prepared['submission_id']}/confirm",
        headers=SUBMIT_HEADERS,
        json={"confirmation": prepared["confirmation_challenge"]},
    )
    confirmed_response.raise_for_status()
    confirmed = confirmed_response.json()
    terminal = _wait(client, confirmed["run_id"])
    artifact_response = client.get(
        f"/v1/runs/{confirmed['run_id']}/artifact", headers=ADMIN_HEADERS
    )
    artifact_response.raise_for_status()
    invocations_response = client.get(
        f"/v1/runs/{confirmed['run_id']}/invocations", headers=ADMIN_HEADERS
    )
    invocations_response.raise_for_status()
    submission = client.get(
        f"/v1/run-submissions/{prepared['submission_id']}", headers=ADMIN_HEADERS
    ).json()
    return {
        "preflight": prepared,
        "confirmed": confirmed,
        "terminal": terminal,
        "artifact": artifact_response.json(),
        "invocations": invocations_response.json()["invocations"],
        "submission": submission,
    }


def _run_subacceptance(script_name: str, output: Path) -> dict[str, object]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PACKAGE_ROOT)
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script_name), "--output", str(output)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{script_name} failed with {result.returncode}:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    payload = json.loads(output.read_text(encoding="utf-8"))
    if payload.get("state") != "PASSED":
        raise RuntimeError(f"{script_name} did not pass")
    return payload


def _count_rows(database: Path) -> dict[str, int]:
    connection = sqlite3.connect(database)
    try:
        return {
            "tasks": connection.execute("select count(*) from task").fetchone()[0],
            "runs": connection.execute("select count(*) from run").fetchone()[0],
            "submissions": connection.execute(
                "select count(*) from run_submission_preflight"
            ).fetchone()[0],
            "invocations": connection.execute("select count(*) from agent_invocation").fetchone()[0],
            "events": connection.execute("select count(*) from run_event").fetchone()[0],
            "artifacts": connection.execute("select count(*) from artifact").fetchone()[0],
        }
    finally:
        connection.close()


def _summary(payload: dict[str, object]) -> dict[str, object]:
    checks = payload.get("checks") or {}
    workspace = payload.get("acceptance_workspace") or {}
    return {
        "schema_version": payload.get("schema_version"),
        "state": payload.get("state"),
        "check_count": len(checks),
        "checks_passed": sum(1 for value in checks.values() if value is True),
        "cleanup_state": workspace.get("cleanup_state", "COMPLETED"),
        "final_counts": payload.get("final_counts"),
    }


def run_acceptance(output: Path) -> int:
    references_before = {
        item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()
    }
    with AcceptanceWorkspace(step_id="STEP045", output=output) as workspace:
        product_db = workspace.database_dir / "product.sqlite3"
        gateway = ToolFreeMatrixGateway()
        app = create_app(
            project_root=ROOT,
            product_db=product_db,
            artifact_root=workspace.artifact_dir,
            evaluation_db=workspace.database_dir / "evaluation.sqlite3",
            admin_key=ADMIN_KEY,
            run_submitter_key=SUBMITTER_KEY,
            protected_payload_root=workspace.scratch_dir / "payloads",
            protected_payload_key=PAYLOAD_KEY,
            gateway=gateway,
        )
        with TestClient(app) as client:
            unauthorized = client.get("/v1/runtime-scenarios")
            scenario_response = client.get("/v1/runtime-scenarios", headers=ADMIN_HEADERS)
            scenario_response.raise_for_status()
            scenario_catalog = scenario_response.json()
            shell = client.get("/runner")
            javascript = client.get("/runner/assets/runner.js")
            stylesheet = client.get("/runner/assets/runner.css")
            tool_free = _execute_tool_free(client)

        subprocess_dir = workspace.scratch_dir / "subacceptance"
        subprocess_dir.mkdir(parents=True, exist_ok=True)
        scripts = {
            "runner_mcp_artifact_evaluation": "run_step037_acceptance.py",
            "function_tool_and_approval": "run_step038_acceptance.py",
            "native_streaming": "run_step039_acceptance.py",
            "native_handoff": "run_step041_acceptance.py",
            "agent_as_tool": "run_step042_acceptance.py",
            "sqlite_session": "run_step043_acceptance.py",
            "native_guardrail": "run_step044_acceptance.py",
        }
        reports = {
            key: _run_subacceptance(script, subprocess_dir / f"{key}.json")
            for key, script in scripts.items()
        }

        scenario_ids = [item["scenario_id"] for item in scenario_catalog["scenarios"]]
        catalog = WalkingSkeletonScenarioCatalog(ROOT)
        combined_assets = shell.text + javascript.text + stylesheet.text
        references_after = {
            item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()
        }
        db_text = product_db.read_bytes().decode("utf-8", errors="ignore")
        product_counts = _count_rows(product_db)
        all_subreports_pass = all(item.get("state") == "PASSED" for item in reports.values())
        all_subreport_cleanup = all(
            (item.get("acceptance_workspace") or {}).get("cleanup_state", "COMPLETED")
            == "COMPLETED"
            for item in reports.values()
        )
        checks = {
            "scenario_catalog_auth_required": unauthorized.status_code == 401,
            "scenario_catalog_exact_ten": scenario_ids == list(catalog.REQUIRED_SCENARIOS),
            "scenario_catalog_identity_exact": scenario_catalog["catalog_sha256"]
            == catalog.catalog_sha256,
            "all_scenario_agents_and_evaluations_resolved": scenario_response.status_code == 200,
            "runner_scenario_matrix_visible": shell.status_code == 200
            and "scenarioGrid" in shell.text
            and "BASIC AGENT RUNTIME SKELETON" in shell.text,
            "runner_scenario_selection_uses_governed_paths": "applyScenario" in javascript.text
            and "/v1/runtime-scenarios" in javascript.text
            and "/v1/run-submissions/preflight" in javascript.text
            and "/confirm" in javascript.text,
            "runner_has_no_hidden_auto_approval": "/decision" not in javascript.text
            and "Approval Operator" in shell.text,
            "runner_invocation_visibility_exact": "/invocations" in javascript.text
            and "invocationList" in shell.text
            and "workspace none" in javascript.text,
            "runner_streams_remain_separate": "Native SDK ephemeral stream" in shell.text
            and "Canonical persisted Events" in shell.text,
            "tool_free_runner_path_succeeded": tool_free["terminal"]["status"] == "SUCCEEDED"
            and gateway.calls == 1,
            "tool_free_artifact_verified": tool_free["artifact"]["content"]["summary"]
            == "Integrated walking skeleton tool-free path completed.",
            "tool_free_root_invocation_visible": len(tool_free["invocations"]) == 1
            and tool_free["invocations"][0]["invocation_kind"] == "ROOT"
            and tool_free["invocations"][0]["workspace_access"] == "none",
            "tool_free_payload_deleted": tool_free["submission"]["payload_retention_state"]
            == "DELETED",
            "mcp_artifact_evaluation_primitive_passed": reports[
                "runner_mcp_artifact_evaluation"
            ]["state"]
            == "PASSED",
            "function_tool_and_separate_approval_primitive_passed": reports[
                "function_tool_and_approval"
            ]["state"]
            == "PASSED",
            "native_streaming_primitive_passed": reports["native_streaming"]["state"]
            == "PASSED",
            "native_handoff_primitive_passed": reports["native_handoff"]["state"]
            == "PASSED",
            "agent_as_tool_primitive_passed": reports["agent_as_tool"]["state"]
            == "PASSED",
            "sqlite_session_two_turn_primitive_passed": reports["sqlite_session"]["state"]
            == "PASSED",
            "native_guardrail_rejection_primitive_passed": reports["native_guardrail"]["state"]
            == "PASSED",
            "all_seven_primitive_acceptances_passed": all_subreports_pass,
            "all_primitive_workspaces_cleaned": all_subreport_cleanup,
            "no_demo_execution_shortcut_in_runtime": "run_step0" not in read_component_source(ROOT, "runtime.all"),
            "tool_free_product_counts_exact": product_counts
            == {
                "tasks": 1,
                "runs": 1,
                "submissions": 1,
                "invocations": 1,
                "events": 10,
                "artifacts": 1,
            },
            "raw_request_not_persisted": RAW_REQUEST not in db_text,
            "references_unchanged": references_before == references_after,
            "basic_runtime_skeleton_complete": all_subreports_pass
            and len(scenario_ids) == 10
            and tool_free["terminal"]["status"] == "SUCCEEDED",
            "cleanup_completed": True,
        }
        payload = {
            "schema_version": "okcanvas-step045-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "skeleton_state": "BASIC_AGENT_RUNTIME_SKELETON_COMPLETE"
            if all(checks.values())
            else "INCOMPLETE",
            "checks": checks,
            "scenario_catalog": {
                "catalog_id": scenario_catalog["catalog_id"],
                "version": scenario_catalog["version"],
                "catalog_sha256": scenario_catalog["catalog_sha256"],
                "scenario_count": len(scenario_ids),
                "scenario_ids": scenario_ids,
            },
            "tool_free_runner": {
                "run_id": tool_free["confirmed"]["run_id"],
                "submission_id": tool_free["preflight"]["submission_id"],
                "gateway_calls": gateway.calls,
                "final_counts": product_counts,
                "artifact_id": tool_free["artifact"]["artifact_id"],
                "invocation_count": len(tool_free["invocations"]),
            },
            "primitive_acceptances": {key: _summary(value) for key, value in reports.items()},
            "matrix": {
                "tool_free_structured": "STEP045 governed Runner",
                "read_only_function_tool": "STEP038",
                "approval_function_tool": "STEP038 + separate Approval Operator",
                "read_only_mcp": "STEP037",
                "native_sdk_streaming": "STEP039",
                "native_handoff": "STEP041",
                "agent_as_tool": "STEP042",
                "sqlite_session_two_turn": "STEP043",
                "native_guardrail_rejection": "STEP044",
                "artifact_recorded_evaluation": "STEP037",
            },
        }
        final = workspace.finalize(payload)
        final["checks"]["cleanup_completed"] = (
            final["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
        )
        final["state"] = "PASSED" if all(final["checks"].values()) else "FAILED"
        final["skeleton_state"] = (
            "BASIC_AGENT_RUNTIME_SKELETON_COMPLETE"
            if final["state"] == "PASSED"
            else "INCOMPLETE"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(final, ensure_ascii=False, indent=2))
        return 0 if final["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP045_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
