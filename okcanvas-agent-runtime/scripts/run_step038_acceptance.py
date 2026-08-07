from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.core.contracts import (
    AgentStatus,
    CodingAgentResult,
    CodingFinding,
    FindingConfidence,
    FindingSeverity,
    UsageSummary,
)
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import GatewayLifecycleEvent, GenericGatewayRunResult
from okcanvas_agent_runtime.agent.tools.function import (
    FunctionToolApprovalMode,
    FunctionToolRuntimeCatalog,
    build_sdk_function_tool,
    execute_product_tool,
)
from okcanvas_agent_runtime.domain.runs import EventSource
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_runtime.application.approvals import decision_confirmation_challenge
from okcanvas_agent_runtime.application.approvals.testing import DeterministicToolApprovalGateway

ADMIN_KEY = "step038-local-admin-key"
SUBMITTER_KEY = "step038-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SUBMIT_HEADERS = {
    **ADMIN_HEADERS,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
}
MODEL = "deterministic-step038-model"
READ_ONLY_REQUEST = "STEP038 governed read only Function Tool request"
APPROVE_REQUEST = "STEP038 governed approved Function Tool request"
REJECT_REQUEST = "STEP038 governed rejected Function Tool request"


class DeterministicFingerprintGateway:
    def __init__(self) -> None:
        self.calls = 0
        self.tool_calls = 0

    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        self.calls += 1
        runtime = FunctionToolRuntimeCatalog(ROOT).resolve_many(definition.tools)[0]
        if runtime.tool_id != "local_text_fingerprint":
            raise RuntimeError("STEP038 deterministic gateway received an unexpected Tool")
        output = execute_product_tool(runtime, request)
        self.tool_calls += 1
        await lifecycle_sink(
            GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id})
        )
        await lifecycle_sink(
            GatewayLifecycleEvent("model.started", {"model": settings.model})
        )
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "tool.started",
                {
                    "tool_id": runtime.tool_id,
                    "tool_name": runtime.tool_id,
                    "runtime_version": runtime.runtime_version,
                    "approval_required": False,
                    "tool_call_id_present": True,
                    "arguments_persisted": False,
                },
                payload_schema_version="okcanvas-function-tool-started-v1",
                source=EventSource.AGENT_SDK,
            )
        )
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "tool.completed",
                {
                    "tool_id": runtime.tool_id,
                    "tool_name": runtime.tool_id,
                    "runtime_version": runtime.runtime_version,
                    "approval_required": False,
                    "tool_call_id_present": True,
                    "result_present": True,
                    "result_persisted": False,
                },
                payload_schema_version="okcanvas-function-tool-completed-v1",
                source=EventSource.AGENT_SDK,
            )
        )
        await lifecycle_sink(
            GatewayLifecycleEvent("model.completed", {"response_id": "resp-step038-read-only"})
        )
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "agent.completed", {"output_contract": definition.output_contract}
            )
        )
        return GenericGatewayRunResult(
            output=CodingAgentResult(
                status=AgentStatus.PASS,
                summary="The governed read-only Function Tool completed.",
                findings=[
                    CodingFinding(
                        severity=FindingSeverity.INFO,
                        confidence=FindingConfidence.CONFIRMED,
                        title="Protected text fingerprint",
                        detail=(
                            f"characters={output.characters}, utf8_bytes={output.utf8_bytes}, "
                            f"sha256={output.sha256}"
                        ),
                        evidence=["local_text_fingerprint registered execution"],
                    )
                ],
                unverified=[],
            ),
            usage=UsageSummary(
                requests=1,
                input_tokens=24,
                output_tokens=18,
                total_tokens=42,
            ),
            trace_id="trace-step038-read-only",
            response_id="resp-step038-read-only",
            sdk_version="0.19.0",
        )


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


def _product_counts(database: Path) -> dict[str, int]:
    connection = sqlite3.connect(database)
    try:
        return {
            "tasks": int(connection.execute("SELECT COUNT(*) FROM task").fetchone()[0]),
            "runs": int(connection.execute("SELECT COUNT(*) FROM run").fetchone()[0]),
            "submissions": int(
                connection.execute("SELECT COUNT(*) FROM run_submission_preflight").fetchone()[0]
            ),
            "artifacts": int(connection.execute("SELECT COUNT(*) FROM artifact").fetchone()[0]),
            "approvals": int(
                connection.execute("SELECT COUNT(*) FROM governed_tool_approval").fetchone()[0]
            ),
        }
    finally:
        connection.close()


def _evaluation_count(database: Path) -> int:
    connection = sqlite3.connect(database)
    try:
        return int(connection.execute("SELECT COUNT(*) FROM evaluation_result").fetchone()[0])
    finally:
        connection.close()


def _wait_terminal(client: TestClient, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        body = client.get(f"/v1/runs/{run_id}", headers=ADMIN_HEADERS).json()
        if body.get("status") in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return body
        time.sleep(0.02)
    raise RuntimeError("STEP038 Run did not reach a terminal state")


def _event_list(client: TestClient, run_id: str) -> list[dict[str, Any]]:
    response = client.get(f"/v1/runs/{run_id}/events", headers=ADMIN_HEADERS)
    if response.status_code != 200:
        raise RuntimeError(f"STEP038 event read failed: {response.text}")
    return response.json()["events"]


def _sdk_factory_probe(catalog: FunctionToolRuntimeCatalog) -> dict[str, Any]:
    runtime = catalog.resolve("local_text_fingerprint")
    execution_id = "execution_" + "a" * 32
    try:
        tool = build_sdk_function_tool(
            runtime,
            execution_id=execution_id,
            protected_text="STEP038 SDK factory probe",
        )
    except Exception as exc:  # package build environment intentionally may not install SDK
        return {
            "installed_sdk_available": False,
            "error_type": type(exc).__name__,
        }
    needs_approval = getattr(tool, "needs_approval", None)
    return {
        "installed_sdk_available": True,
        "tool_name": str(getattr(tool, "name", "")),
        "strict_json_schema": bool(getattr(tool, "strict_json_schema", False)),
        "needs_approval_is_callable": callable(needs_approval),
        "runtime_tool_id": str(getattr(tool, "_okcanvas_function_tool_id", "")),
    }


def run_acceptance(output: Path) -> int:
    os.environ.setdefault("OPENAI_API_KEY", "step038-not-a-real-api-key")
    references_before = {
        item.reference_id: item.to_dict()
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    catalog = FunctionToolRuntimeCatalog(ROOT)
    runtimes = catalog.list_runtimes()
    sdk_probe = _sdk_factory_probe(catalog)

    with AcceptanceWorkspace(step_id="STEP038", output=output) as workspace:
        product_db = workspace.database_dir / "product.sqlite3"
        evaluation_db = workspace.database_dir / "evaluation.sqlite3"
        payload_root = workspace.scratch_dir / "protected-payloads"
        run_state_root = workspace.scratch_dir / "run-states"
        generic_gateway = DeterministicFingerprintGateway()
        approval_gateway = CountingApprovalGateway()
        app = create_app(
            project_root=ROOT,
            product_db=product_db,
            artifact_root=workspace.artifact_dir,
            evaluation_db=evaluation_db,
            admin_key=ADMIN_KEY,
            gateway=generic_gateway,
            run_submitter_key=SUBMITTER_KEY,
            protected_payload_root=payload_root,
            protected_payload_key=PAYLOAD_KEY,
            run_state_root=run_state_root,
            tool_approval_gateway=approval_gateway,
        )

        with TestClient(app) as client:
            agents = client.get("/v1/agent-definitions", headers=ADMIN_HEADERS).json()
            evaluations = client.get("/v1/evaluation-cases", headers=ADMIN_HEADERS).json()

            # Read-only Function Tool path.
            read_preflight = client.post(
                "/v1/run-submissions/preflight",
                headers=SUBMIT_HEADERS,
                json={
                    "agent_definition_id": "local-text-fingerprint-agent",
                    "input": READ_ONLY_REQUEST,
                    "model": MODEL,
                    "idempotency_key": "step038-read-only-idempotency-0001",
                },
            ).json()
            read_confirm = client.post(
                f"/v1/run-submissions/{read_preflight['submission_id']}/confirm",
                headers=SUBMIT_HEADERS,
                json={"confirmation": read_preflight["confirmation_challenge"]},
            )
            read_confirmed = read_confirm.json()
            read_terminal = _wait_terminal(client, read_confirmed["run_id"])
            read_events = _event_list(client, read_confirmed["run_id"])
            read_artifact_response = client.get(
                f"/v1/runs/{read_confirmed['run_id']}/artifact", headers=ADMIN_HEADERS
            )
            read_evaluation_response = client.post(
                f"/v1/runs/{read_confirmed['run_id']}/evaluations",
                headers=ADMIN_HEADERS,
                json={"case_id": "local-text-fingerprint"},
            )
            read_evaluation = read_evaluation_response.json()

            # Approval-required Function Tool, approve branch.
            approve_preflight_response = client.post(
                "/v1/run-submissions/preflight",
                headers=SUBMIT_HEADERS,
                json={
                    "agent_definition_id": "local-text-metrics-agent",
                    "input": APPROVE_REQUEST,
                    "model": MODEL,
                    "idempotency_key": "step038-approve-idempotency-0001",
                },
            )
            approve_preflight = approve_preflight_response.json()
            approve_prepare_response = client.post(
                f"/v1/run-submissions/{approve_preflight['submission_id']}/prepare-approval",
                headers=SUBMIT_HEADERS,
            )
            approve_record = approve_prepare_response.json()
            approve_decision_response = client.post(
                f"/v1/tool-approvals/{approve_record['approval_id']}/decision",
                headers=SUBMIT_HEADERS,
                json={
                    "decision": "APPROVE",
                    "confirmation": decision_confirmation_challenge(
                        approval_id=approve_record["approval_id"],
                        run_id=approve_record["run_id"],
                        decision="APPROVE",
                    ),
                },
            )
            approve_result = approve_decision_response.json()
            approve_replay_response = client.post(
                f"/v1/tool-approvals/{approve_record['approval_id']}/decision",
                headers=SUBMIT_HEADERS,
                json={
                    "decision": "APPROVE",
                    "confirmation": decision_confirmation_challenge(
                        approval_id=approve_record["approval_id"],
                        run_id=approve_record["run_id"],
                        decision="APPROVE",
                    ),
                },
            )
            approve_replay = approve_replay_response.json()
            approve_events = _event_list(client, approve_record["run_id"])
            approve_artifact_response = client.get(
                f"/v1/runs/{approve_record['run_id']}/artifact", headers=ADMIN_HEADERS
            )
            approve_evaluation_response = client.post(
                f"/v1/runs/{approve_record['run_id']}/evaluations",
                headers=ADMIN_HEADERS,
                json={"case_id": "local-text-metrics"},
            )
            approve_evaluation = approve_evaluation_response.json()

            # Approval-required Function Tool, reject branch.
            reject_preflight_response = client.post(
                "/v1/run-submissions/preflight",
                headers=SUBMIT_HEADERS,
                json={
                    "agent_definition_id": "local-text-metrics-agent",
                    "input": REJECT_REQUEST,
                    "model": MODEL,
                    "idempotency_key": "step038-reject-idempotency-0001",
                },
            )
            reject_preflight = reject_preflight_response.json()
            reject_prepare_response = client.post(
                f"/v1/run-submissions/{reject_preflight['submission_id']}/prepare-approval",
                headers=SUBMIT_HEADERS,
            )
            reject_record = reject_prepare_response.json()
            reject_decision_response = client.post(
                f"/v1/tool-approvals/{reject_record['approval_id']}/decision",
                headers=SUBMIT_HEADERS,
                json={
                    "decision": "REJECT",
                    "confirmation": decision_confirmation_challenge(
                        approval_id=reject_record["approval_id"],
                        run_id=reject_record["run_id"],
                        decision="REJECT",
                    ),
                },
            )
            reject_result = reject_decision_response.json()
            reject_replay_response = client.post(
                f"/v1/tool-approvals/{reject_record['approval_id']}/decision",
                headers=SUBMIT_HEADERS,
                json={
                    "decision": "REJECT",
                    "confirmation": decision_confirmation_challenge(
                        approval_id=reject_record["approval_id"],
                        run_id=reject_record["run_id"],
                        decision="REJECT",
                    ),
                },
            )
            reject_replay = reject_replay_response.json()
            reject_events = _event_list(client, reject_record["run_id"])

        references_after_results = ReferenceCatalogService(ROOT).verify_all()
        references_after = {
            item.reference_id: item.to_dict() for item in references_after_results
        }
        product_counts = _product_counts(product_db)
        evaluation_count = _evaluation_count(evaluation_db)
        payload_files = sorted(payload_root.glob("*.json"))
        database_bytes = product_db.read_bytes() + evaluation_db.read_bytes()
        all_events = read_events + approve_events + reject_events
        event_bytes = json.dumps(all_events, sort_keys=True).encode("utf-8")

        runtime_map = {item.tool_id: item for item in runtimes}
        read_tool_events = [
            item for item in read_events if item["event_type"] in {"tool.started", "tool.completed"}
        ]
        approve_tool_events = [
            item for item in approve_events if item["event_type"] in {"tool.started", "tool.completed"}
        ]
        reject_tool_events = [
            item for item in reject_events if item["event_type"] in {"tool.started", "tool.completed"}
        ]
        fingerprint_sha = hashlib.sha256(READ_ONLY_REQUEST.encode("utf-8")).hexdigest()

        agent_items = agents.get("definitions", agents.get("agents", agents.get("items", [])))
        eval_items = evaluations.get("cases", evaluations.get("items", []))
        agent_ids = {item.get("agent_id") for item in agent_items}
        case_ids = {item.get("case_id") for item in eval_items}
        safe_metadata = all(
            (item.get("payload") or {}).get("arguments_persisted") is False
            if item["event_type"] == "tool.started"
            else (item.get("payload") or {}).get("result_persisted") is False
            for item in read_tool_events + approve_tool_events
        )

        checks = {
            "function_tool_registry_contains_expected_modes_and_project_inspection": set(runtime_map) == {
                "local_text_fingerprint",
                "local_text_metrics",
                "project_readonly_inspect",
            },
            "read_only_tool_mode_exact": runtime_map["local_text_fingerprint"].approval_mode
            is FunctionToolApprovalMode.NEVER,
            "approval_tool_mode_exact": runtime_map["local_text_metrics"].approval_mode
            is FunctionToolApprovalMode.ALWAYS,
            "tool_contracts_runtime_bound": all(
                all(
                    value
                    for value in (
                        item.definition_sha256,
                        item.policy_sha256,
                        item.input_schema_sha256,
                        item.output_schema_sha256,
                        item.implementation_sha256,
                    )
                )
                for item in runtimes
            ),
            "agent_and_evaluation_catalogs_include_both_modes": {
                "local-text-fingerprint-agent",
                "local-text-metrics-agent",
            }.issubset(agent_ids)
            and {"local-text-fingerprint", "local-text-metrics"}.issubset(case_ids),
            "read_only_preflight_scheduled_existing_path": read_confirm.status_code == 202
            and read_confirmed.get("scheduled") is True,
            "read_only_run_succeeded": read_terminal.get("status") == "SUCCEEDED",
            "read_only_tool_executed_once": generic_gateway.calls == 1
            and generic_gateway.tool_calls == 1
            and [item["event_type"] for item in read_tool_events]
            == ["tool.started", "tool.completed"],
            "read_only_artifact_verified": read_artifact_response.status_code == 200
            and fingerprint_sha in json.dumps(read_artifact_response.json(), sort_keys=True),
            "read_only_evaluation_passed": read_evaluation_response.status_code == 201
            and read_evaluation.get("state") == "PASSED",
            "approval_prepared_twice": approval_gateway.prepare_calls == 2
            and approve_prepare_response.status_code == 202
            and reject_prepare_response.status_code == 202,
            "approved_tool_executed_exactly_once": approve_decision_response.status_code == 200
            and approve_result.get("state") == "SUCCEEDED"
            and approve_result.get("tool_executed") is True
            and approve_result.get("approval", {}).get("tool_execution_count") == 1
            and [item["event_type"] for item in approve_tool_events]
            == ["tool.started", "tool.completed"],
            "approved_decision_replay_exact": approve_replay_response.status_code == 200
            and approve_replay.get("replayed") is True
            and approve_replay.get("approval", {}).get("tool_execution_count") == 1,
            "approved_artifact_and_evaluation_passed": approve_artifact_response.status_code == 200
            and approve_evaluation_response.status_code == 201
            and approve_evaluation.get("state") == "PASSED",
            "rejected_tool_never_executed": reject_decision_response.status_code == 200
            and reject_result.get("state") == "CANCELLED"
            and reject_result.get("tool_executed") is False
            and reject_result.get("approval", {}).get("tool_execution_count") == 0
            and not reject_tool_events,
            "rejected_decision_replay_exact": reject_replay_response.status_code == 200
            and reject_replay.get("replayed") is True
            and reject_replay.get("approval", {}).get("tool_execution_count") == 0,
            "shared_registry_serves_both_execution_modes": approval_gateway.resume_calls == 2
            and generic_gateway.calls == 1,
            "tool_event_metadata_is_safe": safe_metadata,
            "raw_inputs_not_in_product_or_evaluation_db": all(
                value.encode("utf-8") not in database_bytes
                for value in (READ_ONLY_REQUEST, APPROVE_REQUEST, REJECT_REQUEST)
            ),
            "raw_inputs_and_outputs_not_in_tool_events": all(
                value.encode("utf-8") not in event_bytes
                for value in (READ_ONLY_REQUEST, APPROVE_REQUEST, REJECT_REQUEST, fingerprint_sha)
            ),
            "successful_payloads_deleted_rejected_retained": len(payload_files) == 1
            and payload_files[0].stem == reject_preflight["protected_payload_ref"],
            "final_product_counts_exact": product_counts
            == {
                "tasks": 3,
                "runs": 3,
                "submissions": 3,
                "artifacts": 2,
                "approvals": 2,
            },
            "final_evaluation_count_exact": evaluation_count == 2,
            "references_unchanged": references_before == references_after
            and all(item.verified for item in references_after_results),
        }
        payload = {
            "schema_version": "okcanvas-step038-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "registry_count": len(runtimes),
            "tools": [item.to_public_dict() for item in runtimes],
            "sdk_factory_probe": sdk_probe,
            "read_only": {
                "submission_id": read_preflight["submission_id"],
                "run_id": read_confirmed["run_id"],
                "gateway_calls": generic_gateway.calls,
                "tool_execution_count": generic_gateway.tool_calls,
                "event_types": [item["event_type"] for item in read_events],
                "evaluation_state": read_evaluation.get("state"),
            },
            "approve": {
                "submission_id": approve_preflight["submission_id"],
                "run_id": approve_record["run_id"],
                "approval_id": approve_record["approval_id"],
                "tool_execution_count": approve_result.get("approval", {}).get(
                    "tool_execution_count"
                ),
                "replayed": approve_replay.get("replayed"),
                "evaluation_state": approve_evaluation.get("state"),
                "event_types": [item["event_type"] for item in approve_events],
            },
            "reject": {
                "submission_id": reject_preflight["submission_id"],
                "run_id": reject_record["run_id"],
                "approval_id": reject_record["approval_id"],
                "tool_execution_count": reject_result.get("approval", {}).get(
                    "tool_execution_count"
                ),
                "replayed": reject_replay.get("replayed"),
                "event_types": [item["event_type"] for item in reject_events],
            },
            "gateway_counts": {
                "generic": generic_gateway.calls,
                "approval_prepare": approval_gateway.prepare_calls,
                "approval_resume": approval_gateway.resume_calls,
            },
            "final_counts": {**product_counts, "evaluations": evaluation_count},
            "protected_payload_file_count": len(payload_files),
        }
        final = workspace.finalize(payload)
    print(json.dumps(final, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if final["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP038_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
