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
from urllib.parse import unquote

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.verticals.store_replenishment import build_store_replenishment_result
from okcanvas_agent_runtime.verticals.commerce_snapshot_ingress import CommerceSnapshotAdapterCatalog
from okcanvas_agent_runtime.core.contracts import StoreReplenishmentReviewResult, UsageSummary
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import GatewayLifecycleEvent, GenericGatewayRunResult
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step026-acceptance-admin-key"
SUBMITTER_KEY = "step026-acceptance-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SOURCE_TOKEN = "step026-loopback-source-token-sentinel"
HEADERS = {
    "X-OKCanvas-Admin-Key": ADMIN_KEY,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
}
CASE_ROOT = ROOT / "specs" / "business-cases" / "store-replenishment-review"
VALID_CASES = (
    ("case001-shortage", "store-replenishment-case001"),
    ("case002-covered", "store-replenishment-case002-covered"),
    ("case003-tie-ordering", "store-replenishment-case003-tie-ordering"),
    ("case004-single-shortage", "store-replenishment-case004-single-shortage"),
)
INVALID_CASE = "case005-invalid-duplicate-sku"


def _canonical(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _expected_business_view(payload: dict[str, object]) -> dict[str, object]:
    return {
        "status": payload["status"],
        "snapshot_id": payload["snapshot_id"],
        "reviewed_skus": payload["reviewed_skus"],
        "total_reorder_units": payload["total_reorder_units"],
        "recommendations": [
            {
                "sku": item["sku"],
                "reorder_units": item["reorder_units"],
                "action": item["action"],
            }
            for item in payload["recommendations"]
        ],
    }


class DeterministicMultiCaseGateway:
    def __init__(self, expected_requests: set[str]) -> None:
        self.expected_requests = expected_requests
        self.requests: list[str] = []

    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        assert request in self.expected_requests
        assert request not in self.requests
        self.requests.append(request)
        assert definition.agent_id == "store-replenishment-review-agent"
        assert definition.tools == ()
        assert definition.mcp_servers == ()
        assert definition.handoffs == ()
        snapshot_id = json.loads(request)["snapshot_id"]
        response_id = f"resp_step026_{snapshot_id}"
        await lifecycle_sink(
            GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id})
        )
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        await lifecycle_sink(
            GatewayLifecycleEvent("model.completed", {"response_id": response_id})
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
            trace_id=f"trace_step026_{snapshot_id}",
            response_id=response_id,
            sdk_version="0.19.0",
        )


class ControlledMultiCaseSource:
    def __init__(self, payloads: dict[str, dict[str, object]]) -> None:
        self.payloads = payloads
        self.read_count = 0
        self.reads_by_key: dict[str, int] = {key: 0 for key in payloads}
        self.write_count = 0
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "ControlledMultiCaseSource":
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:  # noqa: N802
                owner.read_count += 1
                prefix = "/v1/inventory-snapshots/"
                if not self.path.startswith(prefix):
                    self.send_error(404)
                    return
                key = unquote(self.path[len(prefix) :])
                if key not in owner.payloads:
                    self.send_error(404)
                    return
                owner.reads_by_key[key] += 1
                if self.headers.get("Authorization") != f"Bearer {SOURCE_TOKEN}":
                    self.send_error(401)
                    return
                body = json.dumps(
                    owner.payloads[key], ensure_ascii=False, indent=2
                ).encode("utf-8")
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
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        payload = client.get(f"/v1/runs/{run_id}", headers=HEADERS).json()
        if payload.get("status") in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return payload
        time.sleep(0.05)
    raise RuntimeError(f"STEP026 Run did not reach a terminal state: {run_id}")


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
    payloads = {
        path.name: json.loads((path / "input.json").read_text(encoding="utf-8"))
        for path in sorted(CASE_ROOT.iterdir())
        if path.is_dir() and (path / "input.json").is_file()
    }
    expected = {
        case_id: _expected_business_view(
            json.loads((CASE_ROOT / case_id / "expected.json").read_text(encoding="utf-8"))
        )
        for case_id, _evaluation_id in VALID_CASES
    }
    canonical_requests = {
        case_id: _canonical(payloads[case_id]) for case_id, _evaluation_id in VALID_CASES
    }
    gateway = DeterministicMultiCaseGateway(set(canonical_requests.values()))
    adapter = CommerceSnapshotAdapterCatalog(ROOT).resolve("controlled-commerce-http")
    references_before = {
        item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()
    }

    with AcceptanceWorkspace(step_id="STEP026", output=output) as workspace:
        product_db = workspace.database_dir / "product.sqlite3"
        evaluation_db = workspace.database_dir / "evaluation.sqlite3"
        case_results: list[dict[str, object]] = []
        all_events: list[dict[str, object]] = []
        replay_ok = False
        replay_read_count = None

        with ControlledMultiCaseSource(payloads) as source:
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
                for index, (case_id, evaluation_id) in enumerate(VALID_CASES, start=1):
                    request_body = {
                        "source_adapter_id": "controlled-commerce-http",
                        "snapshot_key": case_id,
                        "model": "step026-acceptance-model",
                        "idempotency_key": f"step026-{case_id}-idempotency",
                    }
                    preflight_response = client.post(
                        "/v1/commerce-snapshot-ingress/preflight",
                        headers=HEADERS,
                        json=request_body,
                    )
                    preflight = preflight_response.json()
                    if index == 1:
                        before_replay = source.read_count
                        replay_response = client.post(
                            "/v1/commerce-snapshot-ingress/preflight",
                            headers=HEADERS,
                            json=request_body,
                        )
                        replay = replay_response.json()
                        replay_read_count = source.read_count - before_replay
                        replay_ok = (
                            replay_response.status_code == 201
                            and replay.get("submission_id") == preflight.get("submission_id")
                            and replay_read_count == 0
                        )
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
                    all_events.extend(events)
                    outcome_response = client.get(
                        f"/v1/runs/{confirmed['run_id']}/outcome", headers=HEADERS
                    )
                    outcome = outcome_response.json()
                    evaluation_response = client.post(
                        f"/v1/runs/{confirmed['run_id']}/evaluations",
                        headers=HEADERS,
                        json={"case_id": evaluation_id},
                    )
                    evaluation = evaluation_response.json()
                    submission = client.get(
                        f"/v1/run-submissions/{preflight['submission_id']}", headers=HEADERS
                    ).json()
                    case_results.append(
                        {
                            "case_id": case_id,
                            "evaluation_case_id": evaluation_id,
                            "preflight_status": preflight_response.status_code,
                            "before_confirm_counts": before_confirm,
                            "submission_id": preflight.get("submission_id"),
                            "task_id": confirmed.get("task_id"),
                            "run_id": confirmed.get("run_id"),
                            "source_adapter_id": preflight.get("source_adapter_id"),
                            "source_adapter_version": preflight.get("source_adapter_version"),
                            "source_adapter_definition_sha256": preflight.get(
                                "source_adapter_definition_sha256"
                            ),
                            "source_request_sha256": preflight.get("source_request_sha256"),
                            "source_snapshot_sha256": preflight.get("source_snapshot_sha256"),
                            "input_sha256": preflight.get("input_sha256"),
                            "confirm_status": confirm_response.status_code,
                            "scheduled": confirmed.get("scheduled"),
                            "terminal": terminal,
                            "outcome_http_status": outcome_response.status_code,
                            "outcome": outcome,
                            "evaluation_status": evaluation_response.status_code,
                            "evaluation": evaluation,
                            "payload_retention_state": submission.get(
                                "payload_retention_state"
                            ),
                            "event_types": [item["event_type"] for item in events],
                        }
                    )

                counts_before_invalid = _counts(product_db)
                invalid_response = client.post(
                    "/v1/commerce-snapshot-ingress/preflight",
                    headers=HEADERS,
                    json={
                        "source_adapter_id": "controlled-commerce-http",
                        "snapshot_key": INVALID_CASE,
                        "model": "step026-acceptance-model",
                        "idempotency_key": "step026-invalid-duplicate-sku-key",
                    },
                )
                invalid_body = invalid_response.json()
                counts_after_invalid = _counts(product_db)

            source_read_count = source.read_count
            source_reads_by_key = dict(source.reads_by_key)
            source_write_count = source.write_count

        artifact_files = sorted(workspace.artifact_dir.rglob("final-output.json"))
        artifacts: dict[str, dict[str, object]] = {}
        artifact_errors: list[dict[str, str]] = []
        for artifact_file in artifact_files:
            try:
                result = StoreReplenishmentReviewResult.model_validate_json(
                    artifact_file.read_text(encoding="utf-8")
                )
                artifacts[result.snapshot_id] = _expected_business_view(
                    result.model_dump(mode="json")
                )
            except Exception as exc:
                artifact_errors.append(
                    {
                        "path": artifact_file.relative_to(workspace.root).as_posix(),
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )

        database_bytes = product_db.read_bytes()
        event_json = json.dumps(all_events, ensure_ascii=False, sort_keys=True)
        final_counts = _counts(product_db)
        references_after = {
            item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()
        }

        case_contracts_exact = all(artifacts.get(case_id) == expected[case_id] for case_id, _ in VALID_CASES)
        all_preflights_bound = all(
            item["preflight_status"] == 201
            and item["before_confirm_counts"]["tasks"] == index - 1
            and item["before_confirm_counts"]["runs"] == index - 1
            and item["before_confirm_counts"]["submissions"] == index
            and item["source_adapter_id"] == adapter.adapter_id
            and item["source_adapter_version"] == adapter.version
            and item["source_adapter_definition_sha256"] == adapter.definition_sha256
            and item["source_request_sha256"]
            == _sha256_text(_canonical({"snapshot_key": item["case_id"]}))
            and item["source_snapshot_sha256"] == _sha256_text(canonical_requests[item["case_id"]])
            and item["input_sha256"] == item["source_snapshot_sha256"]
            for index, item in enumerate(case_results, start=1)
        )
        all_runs_succeeded = all(
            item["confirm_status"] == 202
            and item["scheduled"] is True
            and item["terminal"].get("status") == "SUCCEEDED"
            and item["outcome_http_status"] == 200
            and item["outcome"].get("status") == "SUCCEEDED"
            for item in case_results
        )
        all_evaluations_passed = all(
            item["evaluation_status"] == 201
            and item["evaluation"].get("state") == "PASSED"
            for item in case_results
        )
        all_payloads_deleted = all(
            item["payload_retention_state"] == "DELETED" for item in case_results
        )
        all_event_types = [item["event_type"] for item in all_events]
        raw_sources_absent = all(
            canonical not in event_json and canonical.encode("utf-8") not in database_bytes
            for canonical in canonical_requests.values()
        )
        checks = {
            "four_valid_business_cases_executed": len(case_results) == 4,
            "valid_source_read_once_per_case": all(
                source_reads_by_key.get(case_id) == 1 for case_id, _ in VALID_CASES
            ),
            "invalid_source_read_once": source_reads_by_key.get(INVALID_CASE) == 1,
            "source_total_reads_exact": source_read_count == 5,
            "source_write_never_called": source_write_count == 0,
            "idempotent_replay_avoided_second_read": replay_ok and replay_read_count == 0,
            "preflights_bound_before_task_or_run": all_preflights_bound,
            "single_task_and_run_per_valid_case": final_counts
            == {"tasks": 4, "runs": 4, "submissions": 4},
            "all_runs_succeeded": all_runs_succeeded,
            "one_artifact_per_valid_case": len(artifact_files) == 4
            and len(artifacts) == 4
            and not artifact_errors,
            "all_business_contracts_exact": case_contracts_exact,
            "covered_case_ready_total_zero": artifacts.get("case002-covered", {}).get("status")
            == "READY"
            and artifacts.get("case002-covered", {}).get("total_reorder_units") == 0,
            "tie_case_sorted_by_sku": [
                item["sku"]
                for item in artifacts.get("case003-tie-ordering", {}).get(
                    "recommendations", []
                )
            ]
            == ["alpha-hub", "zeta-stand", "beta-mouse"],
            "single_shortage_case_total_one": artifacts.get(
                "case004-single-shortage", {}
            ).get("total_reorder_units")
            == 1,
            "all_deterministic_evaluations_passed": all_evaluations_passed,
            "invalid_duplicate_sku_failed_before_persistence": invalid_response.status_code == 502
            and invalid_body.get("code") == "COMMERCE_SNAPSHOT_INVALID"
            and counts_before_invalid == counts_after_invalid,
            "no_tool_or_mcp_events": not any(
                event_type.startswith("tool.") or event_type.startswith("mcp.")
                for event_type in all_event_types
            ),
            "raw_source_snapshots_not_in_events_or_sqlite": raw_sources_absent,
            "credentials_not_in_sqlite": SOURCE_TOKEN.encode("utf-8") not in database_bytes
            and ADMIN_KEY.encode("utf-8") not in database_bytes
            and SUBMITTER_KEY.encode("utf-8") not in database_bytes
            and PAYLOAD_KEY.encode("utf-8") not in database_bytes,
            "all_successful_payloads_deleted": all_payloads_deleted,
            "gateway_called_once_per_valid_case": len(gateway.requests) == 4
            and set(gateway.requests) == set(canonical_requests.values()),
            "references_unchanged": references_before == references_after,
        }
        payload: dict[str, object] = {
            "schema_version": "okcanvas-step026-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "source": {
                "adapter_id": adapter.adapter_id,
                "adapter_version": adapter.version,
                "read_count": source_read_count,
                "reads_by_key": source_reads_by_key,
                "write_count": source_write_count,
            },
            "valid_case_count": len(case_results),
            "invalid_case": {
                "case_id": INVALID_CASE,
                "http_status": invalid_response.status_code,
                "code": invalid_body.get("code"),
                "counts_before": counts_before_invalid,
                "counts_after": counts_after_invalid,
            },
            "case_results": [
                {
                    "case_id": item["case_id"],
                    "submission_id": item["submission_id"],
                    "task_id": item["task_id"],
                    "run_id": item["run_id"],
                    "terminal_status": item["terminal"].get("status"),
                    "outcome_http_status": item["outcome_http_status"],
                    "evaluation_state": item["evaluation"].get("state"),
                    "result": artifacts.get(item["case_id"]),
                    "payload_retention_state": item["payload_retention_state"],
                    "event_types": item["event_types"],
                }
                for item in case_results
            ],
            "artifact_count": len(artifact_files),
            "artifact_errors": artifact_errors,
            "final_counts": final_counts,
        }
        payload = workspace.finalize(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP026_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
