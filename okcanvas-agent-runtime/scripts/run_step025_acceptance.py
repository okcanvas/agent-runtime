from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.verticals.store_replenishment import build_store_replenishment_result
from okcanvas_agent_runtime.verticals.commerce_snapshot_ingress import CommerceSnapshotAdapterCatalog
from okcanvas_agent_runtime.core.contracts import StoreReplenishmentReviewResult, UsageSummary
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import GatewayLifecycleEvent, GenericGatewayRunResult
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step025-acceptance-admin-key"
SUBMITTER_KEY = "step025-acceptance-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SOURCE_TOKEN = "step025-loopback-source-token-sentinel"
HEADERS = {
    "X-OKCanvas-Admin-Key": ADMIN_KEY,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
}
CASE_ROOT = ROOT / "specs" / "business-cases" / "store-replenishment-review" / "case001-shortage"


class DeterministicBusinessGateway:
    def __init__(self, expected_request: str) -> None:
        self.expected_request = expected_request
        self.calls = 0

    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        self.calls += 1
        assert request == self.expected_request
        assert definition.agent_id == "store-replenishment-review-agent"
        assert definition.tools == ()
        assert definition.mcp_servers == ()
        assert definition.handoffs == ()
        await lifecycle_sink(
            GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id})
        )
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        await lifecycle_sink(
            GatewayLifecycleEvent("model.completed", {"response_id": "resp_step025"})
        )
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "agent.completed", {"output_contract": definition.output_contract}
            )
        )
        return GenericGatewayRunResult(
            output=build_store_replenishment_result(request),
            usage=UsageSummary(
                requests=1,
                input_tokens=180,
                output_tokens=220,
                total_tokens=400,
            ),
            trace_id="trace_step025",
            response_id="resp_step025",
            sdk_version="0.19.0",
        )


class ControlledSource:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.read_count = 0
        self.write_count = 0
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "ControlledSource":
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:  # noqa: N802
                owner.read_count += 1
                if self.path != "/v1/inventory-snapshots/case001-shortage":
                    self.send_error(404)
                    return
                if self.headers.get("Authorization") != f"Bearer {SOURCE_TOKEN}":
                    self.send_error(401)
                    return
                body = json.dumps(owner.payload, ensure_ascii=False, indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _reject_write(self) -> None:
                owner.write_count += 1
                self.send_response(405)
                self.send_header("Content-Length", "0")
                self.end_headers()

            do_POST = _reject_write  # type: ignore[assignment]
            do_PUT = _reject_write  # type: ignore[assignment]
            do_PATCH = _reject_write  # type: ignore[assignment]
            do_DELETE = _reject_write  # type: ignore[assignment]

            def log_message(self, _format: str, *args: object) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    @property
    def base_url(self) -> str:
        assert self._server is not None
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"


def _wait_terminal(client: TestClient, run_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        payload = client.get(f"/v1/runs/{run_id}", headers=HEADERS).json()
        if payload.get("status") in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return payload
        time.sleep(0.05)
    raise RuntimeError("STEP025 Run did not reach a terminal state")


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


def run_acceptance(output: Path) -> int:
    source_payload = json.loads((CASE_ROOT / "input.json").read_text(encoding="utf-8"))
    canonical_request = json.dumps(
        source_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    expected_snapshot_sha = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    expected_source_request_sha = hashlib.sha256(
        json.dumps(
            {"snapshot_key": "case001-shortage"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    adapter = CommerceSnapshotAdapterCatalog(ROOT).resolve("controlled-commerce-http")
    references_before = {
        item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()
    }

    with AcceptanceWorkspace(step_id="STEP025", output=output) as workspace:
        product_db = workspace.database_dir / "product.sqlite3"
        evaluation_db = workspace.database_dir / "evaluation.sqlite3"
        gateway = DeterministicBusinessGateway(canonical_request)
        with ControlledSource(source_payload) as source:
            app = create_app(
                project_root=ROOT,
                product_db=product_db,
                artifact_root=workspace.artifact_dir,
                evaluation_db=evaluation_db,
                admin_key=ADMIN_KEY,
                gateway=gateway,
                run_submitter_key=SUBMITTER_KEY,
                protected_payload_root=workspace.scratch_dir / "protected-payloads",
                protected_payload_key=PAYLOAD_KEY,
                commerce_snapshot_environment={
                    "OKCANVAS_COMMERCE_SNAPSHOT_BASE_URL": source.base_url,
                    "OKCANVAS_COMMERCE_SNAPSHOT_BEARER_TOKEN": SOURCE_TOKEN,
                },
            )
            with TestClient(app) as client:
                request_body = {
                    "source_adapter_id": "controlled-commerce-http",
                    "snapshot_key": "case001-shortage",
                    "model": "step025-acceptance-model",
                    "idempotency_key": "step025-commerce-snapshot-case001",
                }
                preflight_response = client.post(
                    "/v1/commerce-snapshot-ingress/preflight",
                    headers=HEADERS,
                    json=request_body,
                )
                preflight = preflight_response.json()
                replay_response = client.post(
                    "/v1/commerce-snapshot-ingress/preflight",
                    headers=HEADERS,
                    json=request_body,
                )
                replay = replay_response.json()
                before_confirm = _counts(product_db)
                confirm_response = client.post(
                    f"/v1/run-submissions/{preflight['submission_id']}/confirm",
                    headers=HEADERS,
                    json={"confirmation": preflight["confirmation_challenge"]},
                )
                confirmed = confirm_response.json()
                terminal = _wait_terminal(client, confirmed["run_id"])
                events = client.get(
                    f"/v1/runs/{confirmed['run_id']}/events", headers=HEADERS
                ).json()["events"]
                outcome_response = client.get(
                    f"/v1/runs/{confirmed['run_id']}/outcome", headers=HEADERS
                )
                outcome = outcome_response.json()
                evaluation_response = client.post(
                    f"/v1/runs/{confirmed['run_id']}/evaluations",
                    headers=HEADERS,
                    json={"case_id": "store-replenishment-case001"},
                )
                evaluation = evaluation_response.json()
                submission = client.get(
                    f"/v1/run-submissions/{preflight['submission_id']}", headers=HEADERS
                ).json()
            source_reads = source.read_count
            source_writes = source.write_count

        artifact_files = list(workspace.artifact_dir.rglob("final-output.json"))
        validated = None
        artifact_error = None
        if len(artifact_files) == 1:
            try:
                validated = StoreReplenishmentReviewResult.model_validate_json(
                    artifact_files[0].read_text(encoding="utf-8")
                )
            except Exception as exc:
                artifact_error = {"error_type": type(exc).__name__, "error": str(exc)}
        else:
            artifact_error = {
                "error_type": "ARTIFACT_COUNT_INVALID",
                "error": f"expected one final-output.json, found {len(artifact_files)}",
            }
        recommendation_map = (
            {item.sku: item.reorder_units for item in validated.recommendations}
            if validated is not None
            else {}
        )
        database_bytes = product_db.read_bytes()
        references_after = {
            item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()
        }
        event_types = [item["event_type"] for item in events]
        event_json = json.dumps(events, ensure_ascii=False, sort_keys=True)
        after = _counts(product_db)
        checks = {
            "loopback_source_read_exactly_once": source_reads == 1,
            "source_write_never_called": source_writes == 0,
            "idempotent_replay_avoided_second_read": replay_response.status_code == 201
            and replay.get("submission_id") == preflight.get("submission_id"),
            "governed_preflight_created": preflight_response.status_code == 201,
            "preflight_created_no_task_or_run": before_confirm["tasks"] == 0
            and before_confirm["runs"] == 0,
            "single_submission_task_and_run": after == {
                "tasks": 1,
                "runs": 1,
                "submissions": 1,
            },
            "adapter_identity_bound": preflight.get("source_adapter_id") == adapter.adapter_id
            and preflight.get("source_adapter_version") == adapter.version
            and preflight.get("source_adapter_definition_sha256")
            == adapter.definition_sha256,
            "source_request_hash_bound": preflight.get("source_request_sha256")
            == expected_source_request_sha,
            "canonical_snapshot_hash_bound": preflight.get("source_snapshot_sha256")
            == expected_snapshot_sha
            and preflight.get("input_sha256") == expected_snapshot_sha,
            "protected_payload_created_before_confirmation": preflight.get(
                "protected_payload_persisted"
            )
            is True,
            "exact_confirmation_scheduled_once": confirm_response.status_code == 202
            and confirmed.get("scheduled") is True,
            "run_succeeded": terminal.get("status") == "SUCCEEDED",
            "artifact_contract_and_formula_exact": validated is not None
            and validated.total_reorder_units == 19
            and recommendation_map
            == {"ergonomic-keyboard": 12, "desk-lamp": 7, "usb-c-dock": 0},
            "deterministic_evaluation_passed": evaluation_response.status_code == 201
            and evaluation.get("state") == "PASSED",
            "no_tool_or_mcp_events": not any(
                item in {"tool.started", "tool.completed"} for item in event_types
            ),
            "source_snapshot_not_in_events": canonical_request not in event_json,
            "source_snapshot_not_in_sqlite": canonical_request.encode("utf-8")
            not in database_bytes,
            "credentials_not_in_sqlite": SOURCE_TOKEN.encode("utf-8") not in database_bytes
            and ADMIN_KEY.encode("utf-8") not in database_bytes
            and SUBMITTER_KEY.encode("utf-8") not in database_bytes
            and PAYLOAD_KEY.encode("utf-8") not in database_bytes,
            "successful_payload_deleted": submission.get("payload_retention_state") == "DELETED",
            "gateway_called_once": gateway.calls == 1,
            "references_unchanged": references_before == references_after,
        }
        artifact_event = next(
            (item for item in events if item.get("event_type") == "artifact.created"), {}
        )
        payload: dict[str, object] = {
            "schema_version": "okcanvas-step025-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "source": {
                "adapter_id": adapter.adapter_id,
                "adapter_version": adapter.version,
                "read_count": source_reads,
                "write_count": source_writes,
            },
            "submission_id": preflight.get("submission_id"),
            "task_id": confirmed.get("task_id"),
            "run_id": confirmed.get("run_id"),
            "artifact_id": artifact_event.get("payload", {}).get("artifact_id"),
            "evaluation_id": evaluation.get("evaluation_id"),
            "terminal": terminal,
            "outcome_http_status": outcome_response.status_code,
            "outcome": outcome,
            "artifact_count": len(artifact_files),
            "artifact_error": artifact_error,
            "result": (
                {
                    "status": validated.status.value,
                    "snapshot_id": validated.snapshot_id,
                    "total_reorder_units": validated.total_reorder_units,
                    "recommendations": [
                        {"sku": item.sku, "reorder_units": item.reorder_units}
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
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP025_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
