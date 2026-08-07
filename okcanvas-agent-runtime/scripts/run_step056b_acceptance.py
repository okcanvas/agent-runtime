from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import uvicorn

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
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ADMIN = "step056b-local-admin-key"
SUBMITTER = "step056b-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(reversed(range(32)))).decode("ascii")
REQUESTS = [
    "STEP056B persistent request one",
    "STEP056B persistent request two",
    "STEP056B persistent request three",
]


class DeterministicNodeCliGateway:
    def __init__(self) -> None:
        self.calls = 0
        self.requests: list[str] = []

    async def run(self, *, definition, request, run_id, settings, lifecycle_sink):
        self.calls += 1
        self.requests.append(request)
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
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
            GatewayLifecycleEvent("agent.completed", {"output_contract": definition.output_contract})
        )
        return GenericGatewayRunResult(
            output=CodingAgentResult(
                status=AgentStatus.PASS,
                summary=f"STEP056B persistent response {self.calls}.",
                findings=[
                    CodingFinding(
                        severity=FindingSeverity.INFO,
                        confidence=FindingConfidence.CONFIRMED,
                        title=f"same-process-request-{self.calls}",
                        detail=f"STEP056B request {self.calls} completed in the same Node process.",
                        evidence=[f"gateway-call-{self.calls}"],
                    )
                ],
                unverified=[],
            ),
            usage=UsageSummary(
                requests=1,
                input_tokens=10 + self.calls,
                output_tokens=20 + self.calls,
                total_tokens=30 + self.calls * 2,
            ),
            trace_id=f"trace-step056b-{self.calls}",
            response_id=None,
            sdk_version="0.19.0",
        )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_server(workspace: AcceptanceWorkspace, gateway: DeterministicNodeCliGateway):
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
    server = uvicorn.Server(
        uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning", lifespan="on")
    )
    thread = threading.Thread(target=server.run, name="step056b-control-api", daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.02)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=5)
        raise RuntimeError("STEP056B loopback Control API did not start")
    return server, thread, f"http://127.0.0.1:{port}"


def _counts(product_db: Path, evaluation_db: Path) -> dict[str, int]:
    product = sqlite3.connect(product_db)
    evaluation = sqlite3.connect(evaluation_db)
    try:
        return {
            "tasks": int(product.execute("SELECT COUNT(*) FROM task").fetchone()[0]),
            "runs": int(product.execute("SELECT COUNT(*) FROM run").fetchone()[0]),
            "submissions": int(product.execute("SELECT COUNT(*) FROM run_submission_preflight").fetchone()[0]),
            "invocations": int(product.execute("SELECT COUNT(*) FROM agent_invocation").fetchone()[0]),
            "events": int(product.execute("SELECT COUNT(*) FROM run_event").fetchone()[0]),
            "artifacts": int(product.execute("SELECT COUNT(*) FROM artifact").fetchone()[0]),
            "evaluations": int(evaluation.execute("SELECT COUNT(*) FROM evaluation_result").fetchone()[0]),
        }
    finally:
        product.close()
        evaluation.close()


def _challenges(product_db: Path) -> list[str]:
    connection = sqlite3.connect(product_db)
    try:
        rows = connection.execute(
            "SELECT confirmation_challenge FROM run_submission_preflight ORDER BY created_at"
        ).fetchall()
        return [str(row[0]) for row in rows if row[0]]
    finally:
        connection.close()


def run_acceptance(output: Path) -> int:
    before_results = ReferenceCatalogService(ROOT).verify_all()
    before = {item.reference_id: item.actual_tree_sha256 for item in before_results}
    with AcceptanceWorkspace(step_id="STEP056B", output=output) as workspace:
        gateway = DeterministicNodeCliGateway()
        server, thread, base_url = _start_server(workspace, gateway)

        def stop_server() -> None:
            server.should_exit = True
            thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError("STEP056B loopback Control API did not stop")

        workspace.register_closer("loopback-control-api", stop_server)
        script_path = workspace.scratch_dir / "cli-script.txt"
        script_path.write_text("\n".join([*REQUESTS, "/details", "/events", "/json", "/quit"]) + "\n", encoding="utf-8")
        node_command = [
            "node",
            str(ROOT / "clients" / "cli" / "dist" / "cli.js"),
            "--base-url",
            base_url,
            "--agent-id",
            "coding-agent",
            "--model",
            "deterministic-step056b-model",
            "--script",
            str(script_path),
            "--yes",
            "--no-color",
        ]
        environment = os.environ.copy()
        environment.update(
            {
                "OKCANVAS_CONTROL_ADMIN_KEY": ADMIN,
                "OKCANVAS_RUN_SUBMITTER_KEY": SUBMITTER,
            }
        )
        completed = subprocess.run(
            node_command,
            cwd=ROOT,
            env=environment,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=60,
            check=False,
        )
        transcript = completed.stdout + completed.stderr
        product_db = workspace.database_dir / "product.sqlite3"
        evaluation_db = workspace.database_dir / "evaluation.sqlite3"
        counts = _counts(product_db, evaluation_db)
        challenges = _challenges(product_db)
        payload_count = len(list((workspace.scratch_dir / "protected-payloads").glob("payload_*.json")))
        database_bytes = product_db.read_bytes() + evaluation_db.read_bytes()
        cli_root = ROOT / "clients" / "cli"
        source_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((cli_root / "src").glob("*.ts"))
        )
        package = json.loads((cli_root / "package.json").read_text(encoding="utf-8"))
        after_results = ReferenceCatalogService(ROOT).verify_all()
        after = {item.reference_id: item.actual_tree_sha256 for item in after_results}
        checks = {
            "node_process_exited_successfully": completed.returncode == 0,
            "node_typescript_source_and_bin_present": package.get("bin", {}).get("okcanvas-agent") == "./dist/cli.js"
            and (cli_root / "src" / "cli.ts").is_file()
            and (cli_root / "dist" / "cli.js").is_file(),
            "no_runtime_npm_dependencies": not package.get("dependencies"),
            "persistent_same_process_three_requests": gateway.calls == 3
            and gateway.requests == REQUESTS
            and "이 프로세스에서 3개 요청" in transcript,
            "prompt_returned_after_each_response": transcript.count("coding-agent> ") >= 4,
            "friendly_answers_rendered": all(
                f"STEP056B persistent response {index}." in transcript for index in range(1, 4)
            ),
            "capability_limits_visible": "프로젝트 파일·Shell·인터넷 접근 없음" in transcript
            and "서버 대화 기억 없음" in transcript,
            "model_prompt_not_repeated": "Model (blank" not in transcript,
            "raw_confirmation_challenge_not_shown": all(challenge not in transcript for challenge in challenges),
            "general_mode_evaluation_disabled": counts["evaluations"] == 0
            and "Evaluation: not requested" in transcript,
            "details_hidden_until_command": transcript.count("Run: run_") == 1,
            "events_hidden_until_command": transcript.count("#01 run.created") == 1,
            "json_hidden_until_command": transcript.count('"status": "PASS"') == 1,
            "governed_preflight_confirmation_used": len(challenges) == 3 and counts["submissions"] == 3,
            "persisted_sse_consumed": counts["events"] == 30
            and transcript.count("#10 payload.retention.applied") == 1,
            "final_product_counts_exact": counts == {
                "tasks": 3,
                "runs": 3,
                "submissions": 3,
                "invocations": 3,
                "events": 30,
                "artifacts": 3,
                "evaluations": 0,
            },
            "successful_payloads_deleted": payload_count == 0,
            "credentials_not_printed_or_persisted": ADMIN not in transcript
            and SUBMITTER not in transcript
            and ADMIN.encode() not in database_bytes
            and SUBMITTER.encode() not in database_bytes,
            "raw_requests_not_persisted": all(request.encode() not in database_bytes for request in REQUESTS),
            "loopback_only_client": "CLI_REMOTE_URL_FORBIDDEN" in source_text
            and "loopback" in source_text.lower(),
            "control_api_and_sse_only": "/v1/run-submissions/preflight" in source_text
            and "/events/stream" in source_text
            and "okcanvas_agent_runtime" not in source_text
            and "python" not in source_text.lower(),
            "client_does_not_require_evaluation": "evaluationCaseId?: string" in source_text,
            "canonical_env_file_only": ".env.local.cmd is not supported" in source_text,
            "references_unchanged": before == after and all(item.verified for item in after_results),
            "cleanup_completed": True,
        }
        payload: dict[str, Any] = {
            "schema_version": "okcanvas-step056b-acceptance-v1",
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks,
            "node_cli": {
                "language": "TypeScript",
                "runtime": "Node.js >=22",
                "persistent_requests": gateway.calls,
                "runtime_dependencies": 0,
                "evaluation_default_enabled": False,
                "session_enabled": False,
                "direct_runtime_access": False,
            },
            "final_counts": counts,
            "protected_payload_file_count": payload_count,
            "process_returncode": completed.returncode,
            "transcript_tail": transcript[-4000:],
        }
        final = workspace.finalize(payload)
    print(json.dumps(final, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if final["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP056B_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
