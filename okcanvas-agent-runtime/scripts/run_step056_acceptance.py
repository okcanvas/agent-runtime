from __future__ import annotations

import argparse
import base64
import json
import socket
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any
import sys

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import uvicorn

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import GatewayLifecycleEvent, GenericGatewayRunResult
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_clients.tui import (
    LocalTUIControlClient,
    TUIApplication,
    TUIClientConfig,
    TUIClientError,
    compatible_agents,
)

ADMIN = "step056-local-admin-key"
SUBMITTER = "step056-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
RAW_REQUEST = "STEP056 governed TUI foundation request sentinel"
WRONG_REQUEST = "STEP056 wrong confirmation request sentinel"


class DeterministicTUIGateway:
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
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "model.completed",
                {
                    "response_id_present": True,
                    "request_id_present": True,
                    "provider_response_id_persisted": False,
                    "provider_request_id_persisted": False,
                },
            )
        )
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "agent.completed", {"output_contract": definition.output_contract}
            )
        )
        return GenericGatewayRunResult(
            output=CodingAgentResult(
                status=AgentStatus.PASS,
                summary="STEP056 governed TUI path completed.",
                findings=[],
                unverified=[],
            ),
            usage=UsageSummary(
                requests=1,
                input_tokens=21,
                output_tokens=13,
                total_tokens=34,
            ),
            trace_id="trace-step056",
            response_id=None,
            sdk_version="0.19.0",
        )


class MemoryTerminal:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, value: str = "") -> None:
        self.lines.append(value)

    def read(self, prompt: str) -> str:
        raise AssertionError(f"Unexpected interactive read: {prompt}")

    def read_secret(self, prompt: str) -> str:
        raise AssertionError(f"Unexpected secret read: {prompt}")

    @property
    def transcript(self) -> str:
        return "\n".join(self.lines)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_server(
    workspace: AcceptanceWorkspace,
    gateway: DeterministicTUIGateway,
) -> tuple[uvicorn.Server, threading.Thread, str]:
    app = create_app(
        project_root=ROOT,
        product_db=workspace.database_dir / "product.sqlite3",
        evaluation_db=workspace.database_dir / "evaluation.sqlite3",
        artifact_root=workspace.artifact_dir,
        admin_key=ADMIN,
        run_submitter_key=SUBMITTER,
        protected_payload_root=workspace.scratch_dir / "protected-payloads",
        protected_payload_key=PAYLOAD_KEY,
        gateway=gateway,
    )
    port = _free_port()
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        lifespan="on",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="step056-control-api", daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.02)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=5)
        raise RuntimeError("STEP056 loopback Control API did not start")
    return server, thread, f"http://127.0.0.1:{port}"


def _product_counts(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(path)
    try:
        return {
            "tasks": int(connection.execute("SELECT COUNT(*) FROM task").fetchone()[0]),
            "runs": int(connection.execute("SELECT COUNT(*) FROM run").fetchone()[0]),
            "submissions": int(
                connection.execute(
                    "SELECT COUNT(*) FROM run_submission_preflight"
                ).fetchone()[0]
            ),
            "invocations": int(
                connection.execute("SELECT COUNT(*) FROM agent_invocation").fetchone()[0]
            ),
            "events": int(connection.execute("SELECT COUNT(*) FROM run_event").fetchone()[0]),
            "artifacts": int(connection.execute("SELECT COUNT(*) FROM artifact").fetchone()[0]),
        }
    finally:
        connection.close()


def _evaluation_count(path: Path) -> int:
    connection = sqlite3.connect(path)
    try:
        return int(connection.execute("SELECT COUNT(*) FROM evaluation_result").fetchone()[0])
    finally:
        connection.close()


def run_acceptance(output: Path) -> int:
    before_results = ReferenceCatalogService(ROOT).verify_all()
    before = {item.reference_id: item.actual_tree_sha256 for item in before_results}
    with AcceptanceWorkspace(step_id="STEP056", output=output) as workspace:
        gateway = DeterministicTUIGateway()
        server, thread, base_url = _start_server(workspace, gateway)

        def stop_server() -> None:
            server.should_exit = True
            thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError("STEP056 loopback Control API did not stop")

        workspace.register_closer("loopback-control-api", stop_server)
        remote_url_rejected = False
        remote_error_code = None
        try:
            TUIClientConfig(
                base_url="http://example.com:8765",
                admin_key=ADMIN,
                submitter_key=SUBMITTER,
            )
        except TUIClientError as exc:
            remote_url_rejected = True
            remote_error_code = exc.code

        config = TUIClientConfig(
            base_url=base_url,
            admin_key=ADMIN,
            submitter_key=SUBMITTER,
            timeout_seconds=30,
        )
        product_db = workspace.database_dir / "product.sqlite3"
        evaluation_db = workspace.database_dir / "evaluation.sqlite3"
        wrong_confirmation_blocked = False
        wrong_error_code = None
        client_closed = False
        terminal = MemoryTerminal()
        with LocalTUIControlClient(config) as client:
            agents = client.list_agents()
            eligible = compatible_agents(agents)
            try:
                TUIApplication(client, MemoryTerminal()).run_once(
                    agent_id="coding-agent",
                    request=WRONG_REQUEST,
                    model="deterministic-step056-model",
                    evaluation_case_id="tui-client-foundation-v1",
                    confirmation_provider=lambda challenge: f"{challenge}-wrong",
                )
            except TUIClientError as exc:
                wrong_confirmation_blocked = True
                wrong_error_code = exc.code
            counts_after_wrong = _product_counts(product_db)
            outcome = TUIApplication(client, terminal).run_once(
                agent_id="coding-agent",
                request=RAW_REQUEST,
                model="deterministic-step056-model",
                evaluation_case_id="tui-client-foundation-v1",
                confirmation_provider=lambda challenge: challenge,
            )
            client_closed = client.closed
        client_closed = client.closed

        final_counts = _product_counts(product_db)
        final_counts["evaluations"] = _evaluation_count(evaluation_db)
        payload_file_count = len(
            list((workspace.scratch_dir / "protected-payloads").glob("payload_*.json"))
        )
        database_bytes = product_db.read_bytes() + evaluation_db.read_bytes()
        event_types = [str(item.get("event_type")) for item in outcome.events]
        sequences = [int(item.get("sequence") or 0) for item in outcome.events]
        source_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((ROOT / "okcanvas_agent_clients" / "tui").glob("*.py"))
        )
        after_results = ReferenceCatalogService(ROOT).verify_all()
        after = {item.reference_id: item.actual_tree_sha256 for item in after_results}
        checks = {
            "loopback_http_used": base_url.startswith("http://127.0.0.1:"),
            "remote_control_api_rejected": remote_url_rejected
            and remote_error_code == "TUI_REMOTE_URL_FORBIDDEN",
            "separate_authorities_required": config.admin_key != config.submitter_key,
            "agent_catalog_loaded": len(agents) >= 1,
            "foundation_filters_tool_session_and_workspace_capabilities": any(
                item.get("agent_id") == "coding-agent" for item in eligible
            )
            and all(
                not item.get("tools")
                and not item.get("mcp_servers")
                and not item.get("handoffs")
                and not item.get("agent_tools")
                and not item.get("guardrails")
                and item.get("session_mode") == "disabled"
                and item.get("workspace_access") == "none"
                for item in eligible
            ),
            "wrong_confirmation_blocked_before_product_state": wrong_confirmation_blocked
            and wrong_error_code == "TUI_CONFIRMATION_MISMATCH"
            and counts_after_wrong["tasks"] == 0
            and counts_after_wrong["runs"] == 0
            and counts_after_wrong["submissions"] == 1,
            "governed_preflight_and_confirmation_used": outcome.preflight.get("submission_id")
            == outcome.confirmed.get("submission", {}).get("submission_id")
            and outcome.confirmed.get("scheduled") is True,
            "persisted_sse_consumed_to_terminal": event_types[0] == "run.created"
            and event_types[-1] == "payload.retention.applied"
            and sequences == list(range(1, len(sequences) + 1)),
            "run_succeeded": outcome.run.get("status") == "SUCCEEDED",
            "single_root_invocation_visible": len(outcome.invocations) == 1
            and outcome.invocations[0].get("invocation_kind") == "ROOT"
            and outcome.invocations[0].get("state") == "SUCCEEDED",
            "verified_artifact_visible": outcome.artifact.get("content", {}).get("status")
            == "PASS"
            and outcome.artifact.get("content", {}).get("summary")
            == "STEP056 governed TUI path completed."
            and outcome.artifact.get("verified_at") is not None,
            "recorded_evaluation_visible": outcome.evaluation.get("state") == "PASSED"
            and outcome.evaluation.get("case_id") == "tui-client-foundation-v1",
            "terminal_transcript_contains_operational_result": "Artifact VERIFIED"
            in terminal.transcript
            and "tui-client-foundation-v1 · PASSED" in terminal.transcript
            and "run.completed" in terminal.transcript,
            "tui_uses_control_api_only": "SQLiteProductStore" not in source_text
            and "OpenAIGenericAgentGateway" not in source_text
            and "create_app" not in source_text
            and "/v1/run-submissions/preflight" in source_text
            and "/events/stream" in source_text,
            "credentials_not_printed_or_persisted": ADMIN not in terminal.transcript
            and SUBMITTER not in terminal.transcript
            and ADMIN.encode() not in database_bytes
            and SUBMITTER.encode() not in database_bytes,
            "raw_requests_not_persisted": RAW_REQUEST.encode() not in database_bytes
            and WRONG_REQUEST.encode() not in database_bytes,
            "successful_payload_deleted_wrong_preflight_retained": payload_file_count == 1,
            "final_product_counts_exact": final_counts
            == {
                "tasks": 1,
                "runs": 1,
                "submissions": 2,
                "invocations": 1,
                "events": 10,
                "artifacts": 1,
                "evaluations": 1,
            },
            "gateway_executed_exactly_once": gateway.calls == 1,
            "client_closed": client_closed,
            "references_unchanged": before == after
            and all(item.verified for item in after_results),
        }
        payload: dict[str, Any] = {
            "schema_version": "okcanvas-step056-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "tui": {
                "mode": "loopback-control-api-persisted-sse",
                "foundation_agent": "coding-agent",
                "evaluation_case": "tui-client-foundation-v1",
                "approval_decision_enabled": False,
                "session_enabled": False,
                "direct_runtime_access": False,
            },
            "submission_id": outcome.preflight.get("submission_id"),
            "task_id": outcome.confirmed.get("task_id"),
            "run_id": outcome.confirmed.get("run_id"),
            "runtime_binding_sha256": outcome.preflight.get("runtime_binding_sha256"),
            "event_count": len(outcome.events),
            "artifact_id": outcome.artifact.get("artifact_id"),
            "evaluation_id": outcome.evaluation.get("evaluation_id"),
            "gateway_call_count": gateway.calls,
            "protected_payload_file_count": payload_file_count,
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
        default=ROOT / "docs" / "evidence" / "STEP056_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
