from __future__ import annotations

import argparse
import base64
import json
import sqlite3
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import GatewayLifecycleEvent, GenericGatewayRunResult
from okcanvas_agent_runtime.domain.runs import EventSource
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ADMIN_KEY = "step037-local-admin-key"
SUBMITTER_KEY = "step037-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SUBMIT_HEADERS = {
    **ADMIN_HEADERS,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
}
RAW_REQUEST = "STEP037 Interactive Runner governed reference research request"
IDEMPOTENCY_KEY = "step037-interactive-runner-idempotency-0001"


class InteractiveReferenceGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        self.calls += 1
        await lifecycle_sink(
            GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id})
        )
        await lifecycle_sink(
            GatewayLifecycleEvent("model.started", {"model": settings.model})
        )
        for tool_name in ("search_reference", "read_reference_file"):
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "tool.started",
                    {
                        "server_id": "reference-catalog",
                        "tool_name": tool_name,
                        "arguments_persisted": False,
                    },
                    source=EventSource.MCP,
                )
            )
            await lifecycle_sink(
                GatewayLifecycleEvent(
                    "tool.completed",
                    {
                        "server_id": "reference-catalog",
                        "tool_name": tool_name,
                        "result_persisted": False,
                    },
                    source=EventSource.MCP,
                )
            )
        await lifecycle_sink(
            GatewayLifecycleEvent("model.completed", {"response_id": "resp-step037"})
        )
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "agent.completed", {"output_contract": definition.output_contract}
            )
        )
        return GenericGatewayRunResult(
            output=CodingAgentResult(
                status=AgentStatus.PARTIAL,
                summary="Interactive Runner completed the governed walking path.",
                findings=[],
                unverified=[],
            ),
            usage=UsageSummary(
                requests=1,
                input_tokens=30,
                output_tokens=14,
                total_tokens=44,
            ),
            trace_id="trace-step037",
            response_id="resp-step037",
            sdk_version="0.19.0",
        )


def _counts(database: Path) -> dict[str, int]:
    connection = sqlite3.connect(database)
    try:
        return {
            "tasks": int(connection.execute("SELECT COUNT(*) FROM task").fetchone()[0]),
            "runs": int(connection.execute("SELECT COUNT(*) FROM run").fetchone()[0]),
            "submissions": int(
                connection.execute(
                    "SELECT COUNT(*) FROM run_submission_preflight"
                ).fetchone()[0]
            ),
            "artifacts": int(connection.execute("SELECT COUNT(*) FROM artifact").fetchone()[0]),
        }
    finally:
        connection.close()


def _wait_terminal(client: TestClient, run_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers=ADMIN_HEADERS)
        body = response.json()
        if body.get("status") in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return body
        time.sleep(0.02)
    raise RuntimeError("STEP037 Run did not reach a terminal state")


def run_acceptance(output: Path) -> int:
    references_before = {
        item.reference_id: item.to_dict()
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    with AcceptanceWorkspace(step_id="STEP037", output=output) as workspace:
        product_db = workspace.database_dir / "product.sqlite3"
        evaluation_db = workspace.database_dir / "evaluation.sqlite3"
        payload_root = workspace.scratch_dir / "protected-payloads"
        gateway = InteractiveReferenceGateway()
        app = create_app(
            project_root=ROOT,
            product_db=product_db,
            artifact_root=workspace.artifact_dir,
            evaluation_db=evaluation_db,
            admin_key=ADMIN_KEY,
            gateway=gateway,
            run_submitter_key=SUBMITTER_KEY,
            protected_payload_root=payload_root,
            protected_payload_key=PAYLOAD_KEY,
        )
        with TestClient(app) as client:
            shell = client.get("/runner")
            css = client.get("/runner/assets/runner.css")
            script = client.get("/runner/assets/runner.js")
            parser = client.get("/runner/assets/persisted-sse.js")
            unauth_catalog = client.get("/v1/agent-definitions")
            admin_only_preflight = client.post(
                "/v1/run-submissions/preflight",
                headers=ADMIN_HEADERS,
                json={
                    "agent_definition_id": "reference-research-agent",
                    "input": RAW_REQUEST,
                    "model": "deterministic-step037-model",
                    "idempotency_key": IDEMPOTENCY_KEY,
                },
            )
            agents = client.get("/v1/agent-definitions", headers=ADMIN_HEADERS).json()
            cases = client.get("/v1/evaluation-cases", headers=ADMIN_HEADERS).json()
            policy = client.get("/v1/run-submission-policy", headers=ADMIN_HEADERS).json()
            preflight_response = client.post(
                "/v1/run-submissions/preflight",
                headers=SUBMIT_HEADERS,
                json={
                    "agent_definition_id": "reference-research-agent",
                    "input": RAW_REQUEST,
                    "model": "deterministic-step037-model",
                    "idempotency_key": IDEMPOTENCY_KEY,
                },
            )
            preflight = preflight_response.json()
            counts_before_confirm = _counts(product_db)
            wrong_confirmation = client.post(
                f"/v1/run-submissions/{preflight['submission_id']}/confirm",
                headers=SUBMIT_HEADERS,
                json={"confirmation": f"{preflight['confirmation_challenge']}-wrong"},
            )
            counts_after_wrong = _counts(product_db)
            confirm_response = client.post(
                f"/v1/run-submissions/{preflight['submission_id']}/confirm",
                headers=SUBMIT_HEADERS,
                json={"confirmation": preflight["confirmation_challenge"]},
            )
            confirmed = confirm_response.json()
            terminal = _wait_terminal(client, confirmed["run_id"])
            events_response = client.get(
                f"/v1/runs/{confirmed['run_id']}/events", headers=ADMIN_HEADERS
            )
            events = events_response.json()["events"]
            artifact_response = client.get(
                f"/v1/runs/{confirmed['run_id']}/artifact", headers=ADMIN_HEADERS
            )
            artifact = artifact_response.json()
            evaluation_response = client.post(
                f"/v1/runs/{confirmed['run_id']}/evaluations",
                headers=ADMIN_HEADERS,
                json={"case_id": "reference-runstate"},
            )
            evaluation = evaluation_response.json()
            evaluation_list = client.get(
                f"/v1/evaluations?subject_run_id={confirmed['run_id']}",
                headers=ADMIN_HEADERS,
            ).json()
            submission_detail = client.get(
                f"/v1/run-submissions/{preflight['submission_id']}",
                headers=ADMIN_HEADERS,
            ).json()

        references_after = {
            item.reference_id: item.to_dict()
            for item in ReferenceCatalogService(ROOT).verify_all()
        }
        assets = shell.text + script.text + parser.text
        database_bytes = product_db.read_bytes() + evaluation_db.read_bytes()
        event_types = [item["event_type"] for item in events]
        final_counts = _counts(product_db)
        checks = {
            "runner_shell_and_assets_served": shell.status_code == 200
            and css.status_code == 200
            and script.status_code == 200
            and parser.status_code == 200,
            "runner_csp_enabled": "default-src 'self'"
            in shell.headers.get("content-security-policy", ""),
            "separate_authority_fields_present": "X-OKCanvas-Admin-Key" in shell.text
            and "X-OKCanvas-Run-Submitter-Key" in shell.text,
            "keys_session_storage_only": "sessionStorage" in script.text
            and "localStorage" not in assets,
            "keys_not_embedded_or_persisted": ADMIN_KEY not in assets
            and SUBMITTER_KEY not in assets
            and ADMIN_KEY.encode() not in database_bytes
            and SUBMITTER_KEY.encode() not in database_bytes
            and PAYLOAD_KEY.encode() not in database_bytes,
            "runner_uses_governed_submission_only": "/v1/run-submissions/preflight"
            in script.text
            and "api('/v1/runs'" not in script.text,
            "runner_has_no_approval_decision": "/decision" not in script.text
            and "/prepare-approval" in script.text,
            "runner_uses_persisted_event_stream": "OKCanvasPersistedSSE.stream"
            in script.text
            and "/events/stream?cursor=" in script.text,
            "catalog_auth_required": unauth_catalog.status_code == 401,
            "submitter_authority_required": admin_only_preflight.status_code == 403
            and admin_only_preflight.json().get("code")
            == "RUN_SUBMITTER_AUTHORITY_REQUIRED",
            "agent_and_evaluation_catalog_loaded": any(
                item.get("agent_id") == "reference-research-agent"
                for item in agents.get("definitions", [])
            )
            and any(
                item.get("case_id") == "reference-runstate"
                for item in cases.get("cases", [])
            ),
            "policy_is_governed_and_console_stays_read_only": policy.get(
                "authority_scope"
            )
            == "LOCAL_RUN_SUBMITTER"
            and policy.get("console_mutation_enabled") is False,
            "preflight_created_without_task_or_run": preflight_response.status_code == 201
            and counts_before_confirm["submissions"] == 1
            and counts_before_confirm["tasks"] == 0
            and counts_before_confirm["runs"] == 0,
            "runtime_binding_and_protected_payload_bound": isinstance(
                preflight.get("runtime_binding_sha256"), str
            )
            and len(preflight["runtime_binding_sha256"]) == 64
            and preflight.get("protected_payload_persisted") is True,
            "wrong_confirmation_created_no_product_state": wrong_confirmation.status_code
            == 409
            and counts_after_wrong == counts_before_confirm,
            "exact_confirmation_scheduled_once": confirm_response.status_code == 202
            and confirmed.get("scheduled") is True
            and gateway.calls == 1,
            "run_completed_through_existing_product_path": terminal.get("status")
            == "SUCCEEDED"
            and final_counts["tasks"] == 1
            and final_counts["runs"] == 1
            and final_counts["artifacts"] == 1,
            "canonical_events_visible": events_response.status_code == 200
            and all(
                required in event_types
                for required in (
                    "run.created",
                    "run.started",
                    "agent.definition.resolved",
                    "model.started",
                    "tool.started",
                    "tool.completed",
                    "artifact.created",
                    "run.completed",
                    "payload.retention.applied",
                )
            ),
            "verified_artifact_read_api_exact": artifact_response.status_code == 200
            and artifact.get("run_id") == confirmed.get("run_id")
            and artifact.get("content", {}).get("status") == "PARTIAL"
            and artifact.get("content", {}).get("summary")
            == "Interactive Runner completed the governed walking path."
            and "storage_path" not in artifact,
            "recorded_evaluation_created": evaluation_response.status_code == 201
            and evaluation.get("state") == "PASSED"
            and evaluation.get("case_id") == "reference-runstate"
            and evaluation.get("subject_runtime_binding_sha256")
            == preflight.get("runtime_binding_sha256"),
            "evaluation_history_contains_run": evaluation_list.get("total") == 1
            and evaluation_list.get("results", [{}])[0].get("subject_run_id")
            == confirmed.get("run_id"),
            "successful_payload_deleted": submission_detail.get(
                "payload_retention_state"
            )
            == "DELETED"
            and len(list(payload_root.glob("payload_*.json"))) == 0,
            "raw_request_not_persisted": RAW_REQUEST.encode() not in database_bytes,
            "references_unchanged": references_before == references_after,
        }
        payload: dict[str, object] = {
            "schema_version": "okcanvas-step037-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "runner": {
                "path": "/runner",
                "authority": "separate-admin-and-run-submitter",
                "approval_decision_enabled": False,
            },
            "submission_id": preflight.get("submission_id"),
            "task_id": confirmed.get("task_id"),
            "run_id": confirmed.get("run_id"),
            "runtime_binding_sha256": preflight.get("runtime_binding_sha256"),
            "event_count": len(events),
            "artifact_id": artifact.get("artifact_id"),
            "evaluation_id": evaluation.get("evaluation_id"),
            "gateway_call_count": gateway.calls,
            "final_counts": final_counts,
        }
        final = workspace.finalize(payload)
    print(json.dumps(final, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if final["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP037_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
