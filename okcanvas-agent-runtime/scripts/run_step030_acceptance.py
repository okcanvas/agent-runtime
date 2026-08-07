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
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ROOT = Path(__file__).resolve().parents[1]
ADMIN_KEY = "step030-acceptance-admin-key"
SUBMITTER_KEY = "step030-acceptance-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SOURCE_TOKEN = "step030-loopback-source-token-sentinel"
SNAPSHOT_KEY = "case006-invalid-empty-items"
HEADERS = {
    "X-OKCanvas-Admin-Key": ADMIN_KEY,
    "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY,
}
EMPTY_SNAPSHOT = {
    "snapshot_id": SNAPSHOT_KEY,
    "safety_stock_units": 2,
    "items": [],
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


class FailIfCalledGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, **_kwargs):
        self.calls += 1
        raise AssertionError("STEP030 empty-inventory rejection must not enter the model gateway")


class EmptyInventorySource:
    def __init__(self) -> None:
        self.read_count = 0
        self.write_count = 0
        self.requested_paths: list[str] = []
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "EmptyInventorySource":
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
                owner.requested_paths.append(key)
                if self.headers.get("Authorization") != f"Bearer {SOURCE_TOKEN}":
                    self._send(401, b"{}")
                    return
                if key != SNAPSHOT_KEY:
                    self._send(404, b"{}")
                    return
                self._send(
                    200,
                    json.dumps(EMPTY_SNAPSHOT, separators=(",", ":")).encode("utf-8"),
                )

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
    with AcceptanceWorkspace(step_id="STEP030", output=output) as workspace:
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

        with EmptyInventorySource() as source:
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
                response = client.post(
                    "/v1/commerce-snapshot-ingress/preflight",
                    headers=HEADERS,
                    json={
                        "source_adapter_id": "controlled-commerce-http",
                        "snapshot_key": SNAPSHOT_KEY,
                        "model": "step030-acceptance-model",
                        "idempotency_key": "step030-empty-inventory-rejection-key",
                    },
                )
                body = response.json()
                counts_final = _counts(product_db, evaluation_db)
            source_read_count = source.read_count
            source_write_count = source.write_count
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
            "empty_inventory_returned_502": response.status_code == 502,
            "empty_inventory_code_exact": body.get("code") == "COMMERCE_SNAPSHOT_INVALID",
            "empty_inventory_not_retryable": body.get("retryable") is False,
            "source_read_exactly_once": source_read_count == 1,
            "requested_path_exact": requested_paths == [SNAPSHOT_KEY],
            "source_write_never_called": source_write_count == 0,
            "product_counts_started_zero": counts_initial == expected_zero,
            "product_counts_remained_zero": counts_final == expected_zero,
            "no_persistent_state_created": counts_initial == counts_final == expected_zero,
            "model_gateway_never_called": gateway.calls == 0,
            "no_artifact_files_created": artifact_files == [],
            "no_protected_payload_files_created": protected_files == [],
            "credential_not_in_sqlite": SOURCE_TOKEN.encode("utf-8") not in database_bytes,
            "empty_snapshot_not_in_sqlite": SNAPSHOT_KEY.encode("utf-8") not in database_bytes,
            "references_unchanged": references_before == references_after,
        }
        payload: dict[str, object] = {
            "schema_version": "okcanvas-step030-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "request": {
                "source_adapter_id": "controlled-commerce-http",
                "snapshot_key": SNAPSHOT_KEY,
            },
            "response": {
                "http_status": response.status_code,
                "code": body.get("code"),
                "message": body.get("message"),
                "retryable": body.get("retryable"),
            },
            "source": {
                "read_count": source_read_count,
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
        default=ROOT / "docs" / "evidence" / "STEP030_ACCEPTANCE.json",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
