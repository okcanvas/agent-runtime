from __future__ import annotations

import argparse
import base64
import json
import socket
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

import httpx
from fastapi.testclient import TestClient

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step027-acceptance-admin-key"
SUBMITTER_KEY = "step027-acceptance-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SOURCE_TOKEN = "step027-loopback-source-token-sentinel"
HEADERS = {
    "X-OKCanvas-Admin-Key": ADMIN_KEY,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
}

NETWORK_CASES = {
    "auth-rejected": (502, "COMMERCE_SNAPSHOT_SOURCE_AUTH_FAILED", False),
    "redirect": (502, "COMMERCE_SNAPSHOT_RESPONSE_REJECTED", False),
    "wrong-content-type": (502, "COMMERCE_SNAPSHOT_RESPONSE_REJECTED", False),
    "oversized": (502, "COMMERCE_SNAPSHOT_RESPONSE_TOO_LARGE", False),
    "malformed-json": (502, "COMMERCE_SNAPSHOT_INVALID", False),
    "invalid-utf8": (502, "COMMERCE_SNAPSHOT_INVALID", False),
    "empty-body": (502, "COMMERCE_SNAPSHOT_INVALID", False),
    "too-many-items": (502, "COMMERCE_SNAPSHOT_INVALID", False),
    "upstream-503": (502, "COMMERCE_SNAPSHOT_RESPONSE_REJECTED", False),
}

NO_NETWORK_CASES = {
    "transport-unavailable": (503, "COMMERCE_SNAPSHOT_SOURCE_UNAVAILABLE", True),
    "missing-configuration": (503, "COMMERCE_SNAPSHOT_SOURCE_NOT_CONFIGURED", False),
    "remote-origin": (503, "COMMERCE_SNAPSHOT_SOURCE_NOT_CONFIGURED", False),
    "invalid-snapshot-key": (422, "COMMERCE_SNAPSHOT_REQUEST_INVALID", False),
    "unknown-adapter": (502, "COMMERCE_SNAPSHOT_DEFINITION_INVALID", False),
}


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


def _valid_snapshot(snapshot_id: str) -> dict[str, object]:
    return {
        "snapshot_id": snapshot_id,
        "safety_stock_units": 2,
        "items": [
            {
                "sku": "step027-safe-sku",
                "available_units": 10,
                "forecast_units": 5,
                "inbound_units": 0,
            }
        ],
    }


class FailIfCalledGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, **_kwargs):
        self.calls += 1
        raise AssertionError("STEP027 failure cases must not enter the model gateway")


class ControlledFailureSource:
    def __init__(self) -> None:
        self.read_count = 0
        self.reads_by_key = {key: 0 for key in NETWORK_CASES}
        self.redirect_target_reads = 0
        self.write_count = 0
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "ControlledFailureSource":
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def _send(self, status: int, body: bytes, content_type: str | None = None, **headers: str) -> None:
                self.send_response(status)
                if content_type is not None:
                    self.send_header("Content-Type", content_type)
                for name, value in headers.items():
                    self.send_header(name.replace("_", "-"), value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    try:
                        self.wfile.write(body)
                    except (BrokenPipeError, ConnectionResetError):
                        pass

            def do_GET(self) -> None:  # noqa: N802
                prefix = "/v1/inventory-snapshots/"
                if not self.path.startswith(prefix):
                    self._send(404, b"")
                    return
                key = unquote(self.path[len(prefix) :])
                if key == "redirect-target":
                    owner.redirect_target_reads += 1
                    body = json.dumps(_valid_snapshot(key)).encode("utf-8")
                    self._send(200, body, "application/json")
                    return
                if key not in NETWORK_CASES:
                    self._send(404, b"")
                    return
                owner.read_count += 1
                owner.reads_by_key[key] += 1
                if self.headers.get("Authorization") != f"Bearer {SOURCE_TOKEN}":
                    self._send(401, b"")
                    return
                if key == "auth-rejected":
                    self._send(401, b"")
                elif key == "redirect":
                    self._send(302, b"", Location="/v1/inventory-snapshots/redirect-target")
                elif key == "wrong-content-type":
                    self._send(200, b"step027-wrong-content-type-sentinel", "text/plain")
                elif key == "oversized":
                    self._send(200, b"x" * 65_537, "application/json")
                elif key == "malformed-json":
                    self._send(200, b'{"step027-malformed-sentinel":', "application/json")
                elif key == "invalid-utf8":
                    self._send(200, b"\xff\xfe", "application/json")
                elif key == "empty-body":
                    self._send(200, b"", "application/json")
                elif key == "too-many-items":
                    payload = {
                        "snapshot_id": "step027-too-many-items-sentinel",
                        "safety_stock_units": 1,
                        "items": [
                            {
                                "sku": f"step027-sku-{index:03d}",
                                "available_units": 1,
                                "forecast_units": 1,
                                "inbound_units": 0,
                            }
                            for index in range(101)
                        ],
                    }
                    self._send(200, json.dumps(payload).encode("utf-8"), "application/json")
                elif key == "upstream-503":
                    self._send(503, b"step027-upstream-503-sentinel", "application/json")

            def do_POST(self) -> None:  # noqa: N802
                owner.write_count += 1
                self._send(405, b"")

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


def _make_app(
    *,
    product_db: Path,
    evaluation_db: Path,
    artifact_root: Path,
    protected_root: Path,
    gateway: FailIfCalledGateway,
    environment: dict[str, str],
    transport: httpx.AsyncBaseTransport | None = None,
):
    return create_app(
        project_root=ROOT,
        product_db=product_db,
        artifact_root=artifact_root,
        evaluation_db=evaluation_db,
        admin_key=ADMIN_KEY,
        gateway=gateway,
        run_submitter_key=SUBMITTER_KEY,
        protected_payload_root=protected_root,
        protected_payload_key=PAYLOAD_KEY,
        commerce_snapshot_environment=environment,
        commerce_snapshot_http_transport=transport,
    )


def _request(client: TestClient, *, case_id: str, adapter_id: str = "controlled-commerce-http", snapshot_key: str | None = None) -> tuple[int, dict[str, object]]:
    response = client.post(
        "/v1/commerce-snapshot-ingress/preflight",
        headers=HEADERS,
        json={
            "source_adapter_id": adapter_id,
            "snapshot_key": snapshot_key if snapshot_key is not None else case_id,
            "model": "step027-acceptance-model",
            "idempotency_key": f"step027-{case_id}-idempotency-key",
        },
    )
    return response.status_code, response.json()


def run(output: Path) -> dict[str, object]:
    references_before = {
        item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()
    }
    with AcceptanceWorkspace(step_id="STEP027", output=output) as workspace:
        product_db = workspace.database_dir / "product.sqlite3"
        evaluation_db = workspace.database_dir / "evaluation.sqlite3"
        protected_root = workspace.scratch_dir / "protected-payloads"
        gateway = FailIfCalledGateway()
        case_results: list[dict[str, object]] = []
        initial_counts: dict[str, int] | None = None

        with ControlledFailureSource() as source:
            app = _make_app(
                product_db=product_db,
                evaluation_db=evaluation_db,
                artifact_root=workspace.artifact_dir,
                protected_root=protected_root,
                gateway=gateway,
                environment={
                    "OKCANVAS_COMMERCE_SNAPSHOT_BASE_URL": source.base_url,
                    "OKCANVAS_COMMERCE_SNAPSHOT_BEARER_TOKEN": SOURCE_TOKEN,
                },
            )
            with TestClient(app) as client:
                initial_counts = _counts(product_db, evaluation_db)
                for case_id, expected in NETWORK_CASES.items():
                    before = _counts(product_db, evaluation_db)
                    status_code, body = _request(client, case_id=case_id)
                    after = _counts(product_db, evaluation_db)
                    case_results.append(
                        {
                            "case_id": case_id,
                            "category": "loopback-http-response",
                            "expected_http_status": expected[0],
                            "expected_code": expected[1],
                            "expected_retryable": expected[2],
                            "http_status": status_code,
                            "code": body.get("code"),
                            "retryable": body.get("retryable"),
                            "counts_before": before,
                            "counts_after": after,
                        }
                    )

            network_read_count = source.read_count
            network_reads_by_key = dict(source.reads_by_key)
            redirect_target_reads = source.redirect_target_reads
            source_write_count = source.write_count

        transport_calls = 0

        async def unavailable_handler(request: httpx.Request) -> httpx.Response:
            nonlocal transport_calls
            transport_calls += 1
            raise httpx.ConnectError("step027 deterministic unavailable", request=request)

        unavailable_app = _make_app(
            product_db=product_db,
            evaluation_db=evaluation_db,
            artifact_root=workspace.artifact_dir,
            protected_root=protected_root,
            gateway=gateway,
            environment={
                "OKCANVAS_COMMERCE_SNAPSHOT_BASE_URL": "http://127.0.0.1:9327",
                "OKCANVAS_COMMERCE_SNAPSHOT_BEARER_TOKEN": SOURCE_TOKEN,
            },
            transport=httpx.MockTransport(unavailable_handler),
        )
        with TestClient(unavailable_app) as client:
            before = _counts(product_db, evaluation_db)
            status_code, body = _request(client, case_id="transport-unavailable")
            after = _counts(product_db, evaluation_db)
            expected = NO_NETWORK_CASES["transport-unavailable"]
            case_results.append({
                "case_id": "transport-unavailable",
                "category": "transport-failure",
                "expected_http_status": expected[0],
                "expected_code": expected[1],
                "expected_retryable": expected[2],
                "http_status": status_code,
                "code": body.get("code"),
                "retryable": body.get("retryable"),
                "counts_before": before,
                "counts_after": after,
            })

        config_cases = [
            (
                "missing-configuration",
                {},
                "controlled-commerce-http",
                "missing-configuration",
            ),
            (
                "remote-origin",
                {
                    "OKCANVAS_COMMERCE_SNAPSHOT_BASE_URL": "http://192.0.2.10:9327",
                    "OKCANVAS_COMMERCE_SNAPSHOT_BEARER_TOKEN": SOURCE_TOKEN,
                },
                "controlled-commerce-http",
                "remote-origin",
            ),
            (
                "invalid-snapshot-key",
                {
                    "OKCANVAS_COMMERCE_SNAPSHOT_BASE_URL": "http://127.0.0.1:9327",
                    "OKCANVAS_COMMERCE_SNAPSHOT_BEARER_TOKEN": SOURCE_TOKEN,
                },
                "controlled-commerce-http",
                "../invalid",
            ),
            (
                "unknown-adapter",
                {
                    "OKCANVAS_COMMERCE_SNAPSHOT_BASE_URL": "http://127.0.0.1:9327",
                    "OKCANVAS_COMMERCE_SNAPSHOT_BEARER_TOKEN": SOURCE_TOKEN,
                },
                "unknown-commerce-adapter",
                "unknown-adapter",
            ),
        ]
        for case_id, environment, adapter_id, snapshot_key in config_cases:
            app = _make_app(
                product_db=product_db,
                evaluation_db=evaluation_db,
                artifact_root=workspace.artifact_dir,
                protected_root=protected_root,
                gateway=gateway,
                environment=environment,
                transport=httpx.MockTransport(unavailable_handler),
            )
            with TestClient(app) as client:
                before = _counts(product_db, evaluation_db)
                status_code, body = _request(
                    client,
                    case_id=case_id,
                    adapter_id=adapter_id,
                    snapshot_key=snapshot_key,
                )
                after = _counts(product_db, evaluation_db)
            expected = NO_NETWORK_CASES[case_id]
            case_results.append({
                "case_id": case_id,
                "category": "pre-network-rejection",
                "expected_http_status": expected[0],
                "expected_code": expected[1],
                "expected_retryable": expected[2],
                "http_status": status_code,
                "code": body.get("code"),
                "retryable": body.get("retryable"),
                "counts_before": before,
                "counts_after": after,
            })

        final_counts = _counts(product_db, evaluation_db)
        references_after = {
            item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()
        }
        database_bytes = product_db.read_bytes() + evaluation_db.read_bytes()
        protected_files = sorted(path for path in protected_root.rglob("*") if path.is_file()) if protected_root.exists() else []
        artifact_files = sorted(path for path in workspace.artifact_dir.rglob("*") if path.is_file())

        exact_results = all(
            item["http_status"] == item["expected_http_status"]
            and item["code"] == item["expected_code"]
            and item["retryable"] is item["expected_retryable"]
            for item in case_results
        )
        no_persistence_per_case = all(
            item["counts_before"] == item["counts_after"] for item in case_results
        )
        expected_zero = {
            "submissions": 0,
            "tasks": 0,
            "runs": 0,
            "events": 0,
            "artifacts": 0,
            "evaluations": 0,
        }
        sensitive_sentinels = (
            SOURCE_TOKEN,
            "step027-wrong-content-type-sentinel",
            "step027-malformed-sentinel",
            "step027-too-many-items-sentinel",
            "step027-upstream-503-sentinel",
        )
        checks = {
            "fourteen_failure_cases_executed": len(case_results) == 14,
            "all_http_statuses_exact": all(item["http_status"] == item["expected_http_status"] for item in case_results),
            "all_error_codes_exact": all(item["code"] == item["expected_code"] for item in case_results),
            "all_retryable_flags_exact": all(item["retryable"] is item["expected_retryable"] for item in case_results),
            "all_failure_contracts_exact": exact_results,
            "network_cases_read_once_each": all(network_reads_by_key.get(key) == 1 for key in NETWORK_CASES),
            "network_total_reads_exact": network_read_count == len(NETWORK_CASES),
            "redirect_not_followed": redirect_target_reads == 0,
            "source_write_never_called": source_write_count == 0,
            "transport_failure_attempted_once": transport_calls == 1,
            "configuration_and_request_failures_before_transport": transport_calls == 1,
            "no_case_created_persistent_state": no_persistence_per_case,
            "initial_product_counts_zero": initial_counts == expected_zero,
            "final_product_counts_zero": final_counts == expected_zero,
            "model_gateway_never_called": gateway.calls == 0,
            "no_artifact_files_created": artifact_files == [],
            "no_protected_payload_files_created": protected_files == [],
            "source_credential_not_in_sqlite": SOURCE_TOKEN.encode("utf-8") not in database_bytes,
            "source_failure_bodies_not_in_sqlite": all(value.encode("utf-8") not in database_bytes for value in sensitive_sentinels[1:]),
            "authentication_failure_is_not_retryable": next(item for item in case_results if item["case_id"] == "auth-rejected")["retryable"] is False,
            "transport_unavailable_is_retryable": next(item for item in case_results if item["case_id"] == "transport-unavailable")["retryable"] is True,
            "invalid_request_returns_422": next(item for item in case_results if item["case_id"] == "invalid-snapshot-key")["http_status"] == 422,
            "missing_and_remote_configuration_return_503": all(next(item for item in case_results if item["case_id"] == key)["http_status"] == 503 for key in ("missing-configuration", "remote-origin")),
            "references_unchanged": references_before == references_after,
        }
        payload: dict[str, object] = {
            "schema_version": "okcanvas-step027-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "failure_case_count": len(case_results),
            "case_results": case_results,
            "source": {
                "adapter_id": "controlled-commerce-http",
                "adapter_version": "1.0.0",
                "network_read_count": network_read_count,
                "network_reads_by_key": network_reads_by_key,
                "redirect_target_reads": redirect_target_reads,
                "transport_attempt_count": transport_calls,
                "write_count": source_write_count,
            },
            "final_counts": final_counts,
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
        default=ROOT / "docs" / "evidence" / "STEP027_ACCEPTANCE.json",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
