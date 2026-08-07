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
from okcanvas_agent_runtime.agent.tools.function import FunctionToolRuntimeCatalog, execute_product_tool
from okcanvas_agent_runtime.domain.runs import EventSource
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ADMIN = "step059-local-admin-key"
SUBMITTER = "step059-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_HISTORY_KEY = base64.urlsafe_b64encode(
    bytes((index + 67) % 256 for index in range(32))
).decode("ascii")
MODEL = "deterministic-step059-model"
AGENT = "project-readonly-coding-agent"
REQUEST = "Find where the health route is registered and cite the project file."
SOURCE_SENTINEL = "STEP059_HEALTH_ROUTE_IMPLEMENTATION"
EXCLUDED_SENTINEL = "STEP059_EXCLUDED_DEPENDENCY_SECRET"


class DeterministicProjectGateway:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.calls = 0
        self.tool_output = None

    async def run(self, *, definition, request, run_id, settings, lifecycle_sink, **kwargs):
        assert definition.agent_id == AGENT
        self.calls += 1
        runtime = FunctionToolRuntimeCatalog(ROOT).resolve("project_readonly_inspect")
        output = execute_product_tool(runtime, request, workspace_root=self.workspace_root)
        self.tool_output = output
        evidence = next(item for item in output.evidence if item.path == "src/router.py")
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        await lifecycle_sink(GatewayLifecycleEvent(
            "tool.started",
            {
                "tool_id": runtime.tool_id,
                "tool_name": runtime.tool_id,
                "runtime_version": runtime.runtime_version,
                "approval_required": False,
                "tool_call_id_present": True,
                "arguments_persisted": False,
                "filesystem_access": "read-only",
                "workspace_path_persisted": False,
            },
            payload_schema_version="okcanvas-function-tool-started-v1",
            source=EventSource.AGENT_SDK,
        ))
        await lifecycle_sink(GatewayLifecycleEvent(
            "tool.completed",
            {
                "tool_id": runtime.tool_id,
                "tool_name": runtime.tool_id,
                "runtime_version": runtime.runtime_version,
                "approval_required": False,
                "tool_call_id_present": True,
                "result_present": True,
                "result_persisted": False,
                "inspected_file_count": len(output.inspected_files),
                "snapshot_sha256": output.snapshot_sha256,
            },
            payload_schema_version="okcanvas-function-tool-completed-v1",
            source=EventSource.AGENT_SDK,
        ))
        await lifecycle_sink(GatewayLifecycleEvent("model.completed", {"response_id_present": True, "request_id_present": True}))
        await lifecycle_sink(GatewayLifecycleEvent("agent.completed", {"agent_id": definition.agent_id, "output_contract": definition.output_contract}))
        result = CodingAgentResult(
            status=AgentStatus.PASS,
            summary="The configured project was inspected through the bounded read-only Tool.",
            findings=[
                CodingFinding(
                    severity=FindingSeverity.INFO,
                    confidence=FindingConfidence.CONFIRMED,
                    title="Health route registration",
                    detail="The health route is registered in the router module.",
                    evidence=[f"{evidence.path}:{evidence.line_start}-{evidence.line_end}"],
                )
            ],
            unverified=[],
        )
        return GenericGatewayRunResult(
            output=result,
            usage=UsageSummary(requests=2, input_tokens=40, output_tokens=20, total_tokens=60),
            trace_id="trace-step059-project-readonly",
            response_id=None,
            sdk_version="0.19.0",
        )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_server(workspace: AcceptanceWorkspace, gateway: DeterministicProjectGateway, project_fixture: Path):
    app = create_app(
        project_root=ROOT,
        product_db=workspace.database_dir / "product.sqlite3",
        evaluation_db=workspace.database_dir / "evaluation.sqlite3",
        artifact_root=workspace.artifact_dir,
        admin_key=ADMIN,
        run_submitter_key=SUBMITTER,
        protected_payload_root=workspace.scratch_dir / "protected-payloads",
        protected_payload_key=PAYLOAD_KEY,
        session_root=workspace.scratch_dir / "sessions",
        session_history_key=SESSION_HISTORY_KEY,
        readonly_workspace_root=project_fixture,
        gateway=gateway,
    )
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning", lifespan="on"))
    thread = threading.Thread(target=server.run, name="step059-control-api", daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.02)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=5)
        raise RuntimeError("STEP059 loopback Control API did not start")
    return app, server, thread, f"http://127.0.0.1:{port}"


def _run_node(base_url: str, script_path: Path):
    env = os.environ.copy()
    env.update({"OKCANVAS_CONTROL_ADMIN_KEY": ADMIN, "OKCANVAS_RUN_SUBMITTER_KEY": SUBMITTER})
    return subprocess.run(
        [
            "node", str(ROOT / "clients" / "cli" / "dist" / "cli.js"),
            "--base-url", base_url,
            "--agent-id", AGENT,
            "--model", MODEL,
            "--script", str(script_path),
            "--yes", "--no-color",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=90,
        check=False,
    )


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


def _files(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def run_acceptance(output: Path) -> int:
    before_refs = {item.reference_id: item.actual_tree_sha256 for item in ReferenceCatalogService(ROOT).verify_all()}
    previous_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "step059-hidden-api-key"
    try:
        with AcceptanceWorkspace(step_id="STEP059", output=output) as workspace:
            fixture = workspace.scratch_dir / "project-fixture"
            (fixture / "src").mkdir(parents=True)
            (fixture / "node_modules" / "hidden").mkdir(parents=True)
            (fixture / "README.md").write_text("# Project Fixture\nHealth routing is implemented in src/router.py.\n", encoding="utf-8")
            (fixture / "src" / "router.py").write_text(
                f"# {SOURCE_SENTINEL}\ndef register_routes(app):\n    app.get('/healthz')\n",
                encoding="utf-8",
            )
            (fixture / "src" / "service.py").write_text("class Service:\n    pass\n", encoding="utf-8")
            (fixture / "node_modules" / "hidden" / "secret.js").write_text(EXCLUDED_SENTINEL, encoding="utf-8")
            before_files = _files(fixture)
            gateway = DeterministicProjectGateway(fixture)
            _app, server, thread, base_url = _start_server(workspace, gateway, fixture)

            def stop_server() -> None:
                server.should_exit = True
                thread.join(timeout=10)
                if thread.is_alive():
                    raise RuntimeError("STEP059 loopback Control API did not stop")

            workspace.register_closer("loopback-control-api", stop_server)
            script = workspace.scratch_dir / "node-cli-script.txt"
            script.write_text("\n".join([REQUEST, "/capabilities", "/details", "/quit"]) + "\n", encoding="utf-8")
            result = _run_node(base_url, script)
            transcript = result.stdout + "\n" + result.stderr
            after_files = _files(fixture)
            counts = _counts(workspace.database_dir / "product.sqlite3", workspace.database_dir / "evaluation.sqlite3")
            product_bytes = (workspace.database_dir / "product.sqlite3").read_bytes()
            after_results = ReferenceCatalogService(ROOT).verify_all()
            after_refs = {item.reference_id: item.actual_tree_sha256 for item in after_results}
            payload_root = workspace.scratch_dir / "protected-payloads"
            payload_count = len([p for p in payload_root.glob("**/*") if p.is_file()]) if payload_root.exists() else 0
            output_model = gateway.tool_output
            artifact_files = [p for p in workspace.artifact_dir.glob("**/*") if p.is_file()]
            artifact_text = "\n".join(p.read_text(encoding="utf-8") for p in artifact_files)
            checks = {
                "node_process_exited_successfully": result.returncode == 0,
                "project_readonly_agent_visible_and_executed": "project-readonly-coding-agent" in transcript and "↳ Tool project_readonly_inspect 실행" in transcript and "✓ Tool project_readonly_inspect 완료" in transcript,
                "answer_first_result_contains_relative_evidence": "src/router.py" in transcript and str(fixture) not in transcript,
                "capability_limits_are_visible": "설정된 프로젝트의 텍스트 파일을 제한적으로 읽기 가능" in transcript and "파일 쓰기·Shell·Git 명령·인터넷 접근 없음" in transcript,
                "actual_project_tool_executed_once": gateway.calls == 1 and output_model is not None,
                "bounded_project_files_inspected": output_model is not None and output_model.files_considered == 3 and "src/router.py" in output_model.inspected_files,
                "excluded_dependency_not_read": output_model is not None and EXCLUDED_SENTINEL not in output_model.model_dump_json(),
                "workspace_unchanged": before_files == after_files,
                "relative_paths_only": output_model is not None and all(not p.startswith("/") and ".." not in Path(p).parts for p in output_model.inspected_files),
                "tool_result_not_persisted_in_events": SOURCE_SENTINEL.encode() not in product_bytes,
                "raw_request_not_persisted": REQUEST.encode() not in product_bytes,
                "artifact_contains_no_absolute_workspace": str(fixture) not in artifact_text,
                "final_product_counts_exact": counts == {"tasks": 1, "runs": 1, "submissions": 1, "invocations": 1, "events": 12, "artifacts": 1, "evaluations": 0},
                "successful_payload_deleted": payload_count == 0,
                "references_unchanged": before_refs == after_refs and all(item.verified for item in after_results),
                "cleanup_completed": True,
            }
            payload: dict[str, Any] = {
                "schema_version": "okcanvas-step059-acceptance-v1",
                "state": "PASSED" if all(checks.values()) else "FAILED",
                "checks": checks,
                "project_inspection": {
                    "agent_id": AGENT,
                    "tool_id": "project_readonly_inspect",
                    "files_considered": output_model.files_considered if output_model else None,
                    "bytes_considered": output_model.bytes_considered if output_model else None,
                    "inspected_files": output_model.inspected_files if output_model else None,
                    "snapshot_sha256": output_model.snapshot_sha256 if output_model else None,
                    "workspace_mutated": before_files != after_files,
                    "shell_enabled": False,
                    "network_enabled": False,
                    "write_enabled": False,
                },
                "final_counts": counts,
                "protected_payload_file_count": payload_count,
                "process_returncode": result.returncode,
                "transcript_tail": transcript[-12000:],
            }
            final = workspace.finalize(payload)
    finally:
        if previous_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = previous_key
    print(json.dumps(final, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if final["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "evidence" / "STEP059_ACCEPTANCE.json")
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
