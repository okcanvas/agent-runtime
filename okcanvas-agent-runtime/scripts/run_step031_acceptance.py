from __future__ import annotations

import argparse
import base64
import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from fastapi.testclient import TestClient

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.verticals.store_replenishment import MAX_INVENTORY_UNIT_VALUE
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step031-acceptance-admin-key"
SUBMITTER_KEY = "step031-acceptance-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SOURCE_TOKEN = "step031-loopback-source-token-sentinel"
HEADERS = {
    "X-OKCanvas-Admin-Key": ADMIN_KEY,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
}
OVER_LIMIT = MAX_INVENTORY_UNIT_VALUE + 1
CASE_IDS = (
    "safety-stock-over-limit",
    "available-over-limit",
    "forecast-over-limit",
    "inbound-over-limit",
    "integer-literal-too-long",
)


def _normal_item(sku: str) -> dict[str, object]:
    return {"sku": sku, "available_units": 1, "forecast_units": 2, "inbound_units": 0}


def _case_body(case_id: str) -> bytes:
    if case_id == "safety-stock-over-limit":
        payload = {
            "snapshot_id": case_id,
            "safety_stock_units": OVER_LIMIT,
            "items": [_normal_item("bounded-a")],
        }
    elif case_id == "available-over-limit":
        payload = {
            "snapshot_id": case_id,
            "safety_stock_units": 1,
            "items": [{**_normal_item("bounded-b"), "available_units": OVER_LIMIT}],
        }
    elif case_id == "forecast-over-limit":
        payload = {
            "snapshot_id": case_id,
            "safety_stock_units": 1,
            "items": [{**_normal_item("bounded-c"), "forecast_units": OVER_LIMIT}],
        }
    elif case_id == "inbound-over-limit":
        payload = {
            "snapshot_id": case_id,
            "safety_stock_units": 1,
            "items": [{**_normal_item("bounded-d"), "inbound_units": OVER_LIMIT}],
        }
    elif case_id == "integer-literal-too-long":
        huge = "9" * 5000
        return (
            '{"snapshot_id":"integer-literal-too-long","safety_stock_units":1,'
            '"items":[{"sku":"bounded-e","available_units":1,'
            f'"forecast_units":{huge},"inbound_units":0}}]'
        ).encode("utf-8")
    else:
        raise KeyError(case_id)
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _counts(product_db: Path, evaluation_db: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    with sqlite3.connect(product_db) as db:
        for key, table in (
            ("submissions", "run_submission_preflight"),
            ("tasks", "task"),
            ("runs", "run"),
            ("events", "run_event"),
            ("artifacts", "artifact"),
        ):
            result[key] = int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    with sqlite3.connect(evaluation_db) as db:
        result["evaluations"] = int(
            db.execute("SELECT COUNT(*) FROM evaluation_result").fetchone()[0]
        )
    return result


class FailIfCalledGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, **_kwargs):
        self.calls += 1
        raise AssertionError("STEP031 quantity rejection must not enter the model gateway")


class BoundedQuantitySource:
    def __init__(self) -> None:
        self.read_count = 0
        self.write_count = 0
        self.reads_by_key: dict[str, int] = {}
        self.requested_paths: list[str] = []
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "BoundedQuantitySource":
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def _send(self, status: int, body: bytes) -> None:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802
                prefix = "/v1/inventory-snapshots/"
                if not self.path.startswith(prefix):
                    self._send(404, b"{}")
                    return
                key = unquote(self.path[len(prefix) :])
                owner.read_count += 1
                owner.reads_by_key[key] = owner.reads_by_key.get(key, 0) + 1
                owner.requested_paths.append(key)
                if self.headers.get("Authorization") != f"Bearer {SOURCE_TOKEN}":
                    self._send(401, b"{}")
                    return
                if key not in CASE_IDS:
                    self._send(404, b"{}")
                    return
                self._send(200, _case_body(key))

            def do_POST(self) -> None:  # noqa: N802
                owner.write_count += 1
                self._send(405, b"{}")

            do_PUT = do_POST
            do_PATCH = do_POST
            do_DELETE = do_POST

            def log_message(self, _format: str, *_args: object) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    @property
    def base_url(self) -> str:
        assert self._server is not None
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)


def run(output: Path) -> dict[str, object]:
    references_before = {
        item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()
    }
    with AcceptanceWorkspace(step_id="STEP031", output=output) as workspace:
        product_db = workspace.database_dir / "product.sqlite3"
        evaluation_db = workspace.database_dir / "evaluation.sqlite3"
        protected_root = workspace.scratch_dir / "protected-payloads"
        gateway = FailIfCalledGateway()
        expected_zero = {
            "submissions": 0,
            "tasks": 0,
            "runs": 0,
            "events": 0,
            "artifacts": 0,
            "evaluations": 0,
        }
        case_results: list[dict[str, object]] = []

        with BoundedQuantitySource() as source:
            app = create_app(
                project_root=ROOT,
                product_db=product_db,
                artifact_root=workspace.artifact_dir,
                evaluation_db=evaluation_db,
                admin_key=ADMIN_KEY,
                gateway=gateway,
                run_submitter_key=SUBMITTER_KEY,
                protected_payload_root=protected_root,
                protected_payload_key=PAYLOAD_KEY,
                commerce_snapshot_environment={
                    "OKCANVAS_COMMERCE_SNAPSHOT_BASE_URL": source.base_url,
                    "OKCANVAS_COMMERCE_SNAPSHOT_BEARER_TOKEN": SOURCE_TOKEN,
                },
            )
            with TestClient(app) as client:
                counts_initial = _counts(product_db, evaluation_db)
                for index, case_id in enumerate(CASE_IDS, start=1):
                    before = _counts(product_db, evaluation_db)
                    response = client.post(
                        "/v1/commerce-snapshot-ingress/preflight",
                        headers=HEADERS,
                        json={
                            "source_adapter_id": "controlled-commerce-http",
                            "snapshot_key": case_id,
                            "model": "step031-acceptance-model",
                            "idempotency_key": f"step031-bounded-quantity-{index:02d}-key",
                        },
                    )
                    body = response.json()
                    after = _counts(product_db, evaluation_db)
                    case_results.append(
                        {
                            "case_id": case_id,
                            "http_status": response.status_code,
                            "code": body.get("code"),
                            "retryable": body.get("retryable"),
                            "counts_before": before,
                            "counts_after": after,
                        }
                    )
                counts_final = _counts(product_db, evaluation_db)
            source_read_count = source.read_count
            source_write_count = source.write_count
            reads_by_key = dict(sorted(source.reads_by_key.items()))
            requested_paths = list(source.requested_paths)

        references_after = {
            item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()
        }
        database_bytes = product_db.read_bytes() + evaluation_db.read_bytes()
        artifact_files = sorted(path for path in workspace.artifact_dir.rglob("*") if path.is_file())
        protected_files = (
            sorted(path for path in protected_root.rglob("*") if path.is_file())
            if protected_root.exists()
            else []
        )
        checks = {
            "five_quantity_limit_cases_executed": len(case_results) == 5,
            "all_http_statuses_502": all(item["http_status"] == 502 for item in case_results),
            "all_error_codes_exact": all(
                item["code"] == "COMMERCE_SNAPSHOT_INVALID" for item in case_results
            ),
            "all_failures_not_retryable": all(item["retryable"] is False for item in case_results),
            "all_quantity_fields_bounded": {item["case_id"] for item in case_results}
            == set(CASE_IDS),
            "overlong_integer_literal_rejected_safely": any(
                item["case_id"] == "integer-literal-too-long"
                and item["http_status"] == 502
                and item["code"] == "COMMERCE_SNAPSHOT_INVALID"
                for item in case_results
            ),
            "source_read_once_per_case": reads_by_key == {key: 1 for key in sorted(CASE_IDS)},
            "source_total_reads_exact": source_read_count == 5,
            "requested_paths_exact": requested_paths == list(CASE_IDS),
            "source_write_never_called": source_write_count == 0,
            "product_counts_started_zero": counts_initial == expected_zero,
            "product_counts_remained_zero": counts_final == expected_zero,
            "no_case_created_persistent_state": all(
                item["counts_before"] == expected_zero and item["counts_after"] == expected_zero
                for item in case_results
            ),
            "model_gateway_never_called": gateway.calls == 0,
            "no_artifact_files_created": artifact_files == [],
            "no_protected_payload_files_created": protected_files == [],
            "credential_not_in_sqlite": SOURCE_TOKEN.encode("utf-8") not in database_bytes,
            "invalid_source_snapshots_not_in_sqlite": all(
                case_id.encode("utf-8") not in database_bytes for case_id in CASE_IDS
            ),
            "references_unchanged": references_before == references_after,
        }
        payload: dict[str, object] = {
            "schema_version": "okcanvas-step031-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "max_inventory_unit_value": MAX_INVENTORY_UNIT_VALUE,
            "case_count": len(case_results),
            "case_results": case_results,
            "source": {
                "read_count": source_read_count,
                "reads_by_key": reads_by_key,
                "requested_paths": requested_paths,
                "write_count": source_write_count,
            },
            "final_counts": counts_final,
            "artifact_count": len(artifact_files),
            "protected_payload_file_count": len(protected_files),
            "gateway_call_count": gateway.calls,
            "checks": checks,
        }
        return workspace.finalize(payload)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP031_ACCEPTANCE.json",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
