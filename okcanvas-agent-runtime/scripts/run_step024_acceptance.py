from __future__ import annotations

import argparse
import base64
import json
import os
import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.core.contracts import (
    StoreReplenishmentReviewResult,
    UsageSummary,
)
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import GatewayLifecycleEvent, GenericGatewayRunResult
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step024-acceptance-admin-key"
SUBMITTER_KEY = "step024-acceptance-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
HEADERS = {
    "X-OKCanvas-Admin-Key": ADMIN_KEY,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
}
CASE_ROOT = ROOT / "specs" / "business-cases" / "store-replenishment-review" / "case001-shortage"


class DeterministicBusinessGateway:
    def __init__(self, expected: StoreReplenishmentReviewResult) -> None:
        self.expected = expected
        self.calls = 0
        self.received_request: str | None = None

    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        self.calls += 1
        self.received_request = request
        assert definition.agent_id == "store-replenishment-review-agent"
        assert definition.tools == ()
        assert definition.mcp_servers == ()
        assert definition.handoffs == ()
        await lifecycle_sink(
            GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id})
        )
        await lifecycle_sink(
            GatewayLifecycleEvent("model.started", {"model": settings.model})
        )
        await lifecycle_sink(
            GatewayLifecycleEvent("model.completed", {"response_id": "resp_step024"})
        )
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "agent.completed", {"output_contract": definition.output_contract}
            )
        )
        return GenericGatewayRunResult(
            output=self.expected,
            usage=UsageSummary(
                requests=1,
                input_tokens=180,
                output_tokens=220,
                total_tokens=400,
            ),
            trace_id="trace_step024",
            response_id="resp_step024",
            sdk_version="0.19.0",
        )


def _wait_terminal(client: TestClient, run_id: str, *, timeout: float) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/v1/runs/{run_id}", headers=HEADERS)
        payload = response.json()
        if payload.get("status") in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return payload
        time.sleep(0.05)
    raise RuntimeError("STEP024 Run did not reach a terminal state")


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


def _default_output(*, live: bool) -> Path:
    if not live:
        return ROOT / "docs" / "evidence" / "STEP024_ACCEPTANCE.json"
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return ROOT / "docs" / "evidence" / "step024-live" / stamp / "acceptance-summary.json"


def run_acceptance(output: Path, *, live: bool) -> int:
    input_payload = json.loads((CASE_ROOT / "input.json").read_text(encoding="utf-8"))
    expected_payload = json.loads((CASE_ROOT / "expected.json").read_text(encoding="utf-8"))
    expected = StoreReplenishmentReviewResult.model_validate(expected_payload)
    raw_request = json.dumps(input_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    model = os.environ.get("OKCANVAS_AGENT_MODEL") if live else "step024-acceptance-model"
    if live and (not os.environ.get("OPENAI_API_KEY") or not model):
        payload = {
            "schema_version": "okcanvas-step024-acceptance-v1",
            "state": "FAILED",
            "live_sdk": True,
            "error_code": "LIVE_RUNTIME_NOT_CONFIGURED",
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 3

    references_before = {
        item.reference_id: item.to_dict()
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    with AcceptanceWorkspace(step_id="STEP024", output=output) as workspace:
        product_db = workspace.database_dir / "product.sqlite3"
        evaluation_db = workspace.database_dir / "evaluation.sqlite3"
        payload_root = workspace.scratch_dir / "protected-payloads"
        gateway = None if live else DeterministicBusinessGateway(expected)
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
            catalog = client.get("/v1/agent-definitions", headers=HEADERS).json()
            preflight_response = client.post(
                "/v1/run-submissions/preflight",
                headers=HEADERS,
                json={
                    "agent_definition_id": "store-replenishment-review-agent",
                    "input": raw_request,
                    "model": model,
                    "idempotency_key": "step024-store-replenishment-case001",
                },
            )
            preflight = preflight_response.json()
            before_confirm = _counts(product_db)
            confirm_response = client.post(
                f"/v1/run-submissions/{preflight['submission_id']}/confirm",
                headers=HEADERS,
                json={"confirmation": preflight["confirmation_challenge"]},
            )
            confirmed = confirm_response.json()
            terminal = _wait_terminal(
                client,
                confirmed["run_id"],
                timeout=120.0 if live else 5.0,
            )
            events = client.get(
                f"/v1/runs/{confirmed['run_id']}/events", headers=HEADERS
            ).json()["events"]
            outcome_response = client.get(
                f"/v1/runs/{confirmed['run_id']}/outcome", headers=HEADERS
            )
            outcome = outcome_response.json()
            if terminal.get("status") == "SUCCEEDED":
                evaluation_response = client.post(
                    f"/v1/runs/{confirmed['run_id']}/evaluations",
                    headers=HEADERS,
                    json={"case_id": "store-replenishment-case001"},
                )
                evaluation = evaluation_response.json()
            else:
                evaluation_response = None
                evaluation = {}
            submission = client.get(
                f"/v1/run-submissions/{preflight['submission_id']}", headers=HEADERS
            ).json()

        artifact_files = list(workspace.artifact_dir.rglob("final-output.json"))
        artifact_payload = None
        validated = None
        artifact_error = None
        if len(artifact_files) == 1:
            try:
                artifact_payload = json.loads(artifact_files[0].read_text(encoding="utf-8"))
                validated = StoreReplenishmentReviewResult.model_validate(artifact_payload)
            except Exception as exc:
                artifact_error = {"error_type": type(exc).__name__, "error": str(exc)}
        else:
            artifact_error = {
                "error_type": "ARTIFACT_COUNT_INVALID",
                "error": f"expected exactly one final-output.json, found {len(artifact_files)}",
            }
        database_bytes = product_db.read_bytes()
        references_after = {
            item.reference_id: item.to_dict()
            for item in ReferenceCatalogService(ROOT).verify_all()
        }
        event_types = [item["event_type"] for item in events]
        output_recovered = "agent.output.recovered" in event_types
        recommendation_map = (
            {item.sku: item for item in validated.recommendations}
            if validated is not None
            else {}
        )
        after = _counts(product_db)
        checks = {
            "business_agent_catalogued": any(
                item.get("agent_id") == "store-replenishment-review-agent"
                for item in catalog.get("definitions", [])
            ),
            "governed_preflight_created": preflight_response.status_code == 201,
            "preflight_created_no_task_or_run": before_confirm["tasks"] == 0
            and before_confirm["runs"] == 0,
            "exact_confirmation_scheduled_once": confirm_response.status_code == 202
            and confirmed.get("scheduled") is True,
            "single_task_and_run_created": after["tasks"] == 1 and after["runs"] == 1,
            "run_succeeded": terminal.get("status") == "SUCCEEDED",
            "business_output_contract_valid": validated is not None
            and validated.status.value == "ACTION_REQUIRED"
            and validated.reviewed_skus == 3
            and validated.total_reorder_units == 19,
            "replenishment_formula_exact": validated is not None
            and recommendation_map.get("ergonomic-keyboard") is not None
            and recommendation_map["ergonomic-keyboard"].reorder_units == 12
            and recommendation_map.get("desk-lamp") is not None
            and recommendation_map["desk-lamp"].reorder_units == 7
            and recommendation_map.get("usb-c-dock") is not None
            and recommendation_map["usb-c-dock"].reorder_units == 0,
            "recommendations_sorted": validated is not None
            and [item.sku for item in validated.recommendations]
            == ["ergonomic-keyboard", "desk-lamp", "usb-c-dock"],
            "no_tool_or_mcp_events": not any(
                item in {"tool.started", "tool.completed"} for item in event_types
            ),
            "canonical_run_completed": "run.completed" in event_types
            and "artifact.created" in event_types
            and event_types.index("run.completed") > event_types.index("artifact.created"),
            "artifact_verified": len(artifact_files) == 1 and validated is not None,
            "deterministic_evaluation_passed": evaluation_response is not None
            and evaluation_response.status_code == 201
            and evaluation.get("state") == "PASSED",
            "raw_input_not_in_product_db": raw_request.encode("utf-8") not in database_bytes,
            "keys_not_in_product_db": ADMIN_KEY.encode() not in database_bytes
            and SUBMITTER_KEY.encode() not in database_bytes
            and PAYLOAD_KEY.encode() not in database_bytes,
            "successful_payload_deleted": submission.get("payload_retention_state") == "DELETED",
            "references_unchanged": references_before == references_after,
            "gateway_called_once": live
            or (isinstance(gateway, DeterministicBusinessGateway) and gateway.calls == 1),
        }
        artifact_event = next(
            (item for item in events if item.get("event_type") == "artifact.created"),
            {},
        )
        payload: dict[str, object] = {
            "schema_version": "okcanvas-step024-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "live_sdk": live,
            "checks": checks,
            "submission_id": preflight.get("submission_id"),
            "task_id": confirmed.get("task_id"),
            "run_id": confirmed.get("run_id"),
            "artifact_id": artifact_event.get("payload", {}).get("artifact_id"),
            "evaluation_id": evaluation.get("evaluation_id"),
            "terminal": terminal,
            "outcome_http_status": outcome_response.status_code,
            "outcome": outcome,
            "artifact_count": len(artifact_files),
            "output_recovered": output_recovered,
            "artifact_error": artifact_error,
            "result": (
                {
                    "status": validated.status.value,
                    "snapshot_id": validated.snapshot_id,
                    "reviewed_skus": validated.reviewed_skus,
                    "total_reorder_units": validated.total_reorder_units,
                    "recommendations": [
                        {
                            "sku": item.sku,
                            "reorder_units": item.reorder_units,
                            "action": item.action.value,
                        }
                        for item in validated.recommendations
                    ],
                }
                if validated is not None
                else None
            ),
            "event_types": event_types,
        }
        payload = workspace.finalize(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or _default_output(live=args.live)
    return run_acceptance(output, live=args.live)


if __name__ == "__main__":
    raise SystemExit(main())
