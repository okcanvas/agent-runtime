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

ADMIN = "step060-local-admin-key"
SUBMITTER = "step060-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_HISTORY_KEY = base64.urlsafe_b64encode(
    bytes((index + 67) % 256 for index in range(32))
).decode("ascii")
MODEL = "deterministic-step060-model"
AGENT = "project-readonly-coding-agent"
REQUEST = "Health API가 어디에서 등록되는지 파일과 라인 근거로 알려줘"
EXCLUDED_SENTINEL = "STEP060_EXCLUDED_DEPENDENCY_SECRET"
UNRELATED_SENTINEL = "STEP060_UNRELATED_ARCHITECTURE_AUDIT"
EXPECTED_PATH = "okcanvas_agent_runtime/control_api/app.py"


class DeterministicQueryDirectedGateway:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.calls = 0
        self.tool_output = None

    async def run(self, *, definition, request, run_id, settings, lifecycle_sink, **kwargs):
        assert definition.agent_id == AGENT
        assert request == REQUEST
        self.calls += 1
        runtime = FunctionToolRuntimeCatalog(ROOT).resolve("project_readonly_inspect")
        output = execute_product_tool(runtime, request, workspace_root=self.workspace_root)
        self.tool_output = output
        evidence = output.evidence[0]
        assert evidence.path == EXPECTED_PATH

        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        await lifecycle_sink(
            GatewayLifecycleEvent(
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
            )
        )
        await lifecycle_sink(
            GatewayLifecycleEvent(
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
            )
        )
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "model.completed",
                {"response_id_present": True, "request_id_present": True},
            )
        )
        await lifecycle_sink(
            GatewayLifecycleEvent(
                "agent.completed",
                {"agent_id": definition.agent_id, "output_contract": definition.output_contract},
            )
        )
        result = CodingAgentResult(
            status=AgentStatus.PASS,
            summary=(
                "Health API는 "
                f"{evidence.path}:{evidence.line_start}-{evidence.line_end}에서 등록됩니다."
            ),
            findings=[
                CodingFinding(
                    severity=FindingSeverity.INFO,
                    confidence=FindingConfidence.CONFIRMED,
                    title="Health API registration",
                    detail="The FastAPI GET /healthz decorator and health handler are adjacent.",
                    evidence=[f"{evidence.path}:{evidence.line_start}-{evidence.line_end}"],
                )
            ],
            unverified=[],
        )
        return GenericGatewayRunResult(
            output=result,
            usage=UsageSummary(requests=2, input_tokens=120, output_tokens=40, total_tokens=160),
            trace_id="trace-step060-query-directed-project-retrieval",
            response_id=None,
            sdk_version="0.19.0",
        )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_server(workspace: AcceptanceWorkspace, gateway: DeterministicQueryDirectedGateway, project_fixture: Path):
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
    server = uvicorn.Server(
        uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning", lifespan="on")
    )
    thread = threading.Thread(target=server.run, name="step060-control-api", daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.02)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=5)
        raise RuntimeError("STEP060 loopback Control API did not start")
    return server, thread, f"http://127.0.0.1:{port}"


def _run_node(base_url: str, script_path: Path):
    env = os.environ.copy()
    env.update({"OKCANVAS_CONTROL_ADMIN_KEY": ADMIN, "OKCANVAS_RUN_SUBMITTER_KEY": SUBMITTER})
    return subprocess.run(
        [
            "node",
            str(ROOT / "clients" / "cli" / "dist" / "cli.js"),
            "--base-url",
            base_url,
            "--agent-id",
            AGENT,
            "--model",
            MODEL,
            "--script",
            str(script_path),
            "--yes",
            "--no-color",
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
            "submissions": int(
                product.execute("SELECT COUNT(*) FROM run_submission_preflight").fetchone()[0]
            ),
            "invocations": int(product.execute("SELECT COUNT(*) FROM agent_invocation").fetchone()[0]),
            "events": int(product.execute("SELECT COUNT(*) FROM run_event").fetchone()[0]),
            "artifacts": int(product.execute("SELECT COUNT(*) FROM artifact").fetchone()[0]),
            "evaluations": int(
                evaluation.execute("SELECT COUNT(*) FROM evaluation_result").fetchone()[0]
            ),
        }
    finally:
        product.close()
        evaluation.close()


def _files(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def _build_fixture(root: Path) -> int:
    (root / "src" / "okcanvas_agent_runtime" / "control_api").mkdir(parents=True)
    (root / "clients" / "cli" / "src").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "docs" / "plans").mkdir(parents=True)
    (root / "node_modules" / "hidden").mkdir(parents=True)
    app_lines = (
        ["from fastapi import FastAPI", "", "app = FastAPI()"]
        + [f"# unrelated implementation line {index}" for index in range(1, 30)]
        + [
            '@app.get("/healthz")',
            "async def health() -> dict[str, object]:",
            '    return {"status": "ok"}',
        ]
    )
    (root / EXPECTED_PATH).write_text("\n".join(app_lines) + "\n", encoding="utf-8")
    (root / "clients" / "cli" / "src" / "api-client.ts").write_text(
        'export async function health() { return request("/healthz"); }\n', encoding="utf-8"
    )
    (root / "tests" / "test_control_api.py").write_text(
        'def test_health(client):\n    assert client.get("/healthz").status_code == 200\n',
        encoding="utf-8",
    )
    (root / "docs" / "plans" / "legacy-health-api.md").write_text(
        (("health api route endpoint registration historical plan " + UNRELATED_SENTINEL + "\n") * 80),
        encoding="utf-8",
    )
    (root / "src" / "okcanvas_agent_runtime" / "control_api" / "auth.py").write_text(
        (("# api authentication boundary " + UNRELATED_SENTINEL + "\n") * 100),
        encoding="utf-8",
    )
    (root / "node_modules" / "hidden" / "secret.js").write_text(EXCLUDED_SENTINEL, encoding="utf-8")
    return app_lines.index('@app.get("/healthz")') + 1


def run_acceptance(output: Path) -> int:
    before_refs = {
        item.reference_id: item.actual_tree_sha256
        for item in ReferenceCatalogService(ROOT).verify_all()
    }
    previous_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "step060-hidden-api-key"
    try:
        with AcceptanceWorkspace(step_id="STEP060", output=output) as workspace:
            fixture = workspace.scratch_dir / "project-fixture"
            expected_route_line = _build_fixture(fixture)
            before_files = _files(fixture)
            gateway = DeterministicQueryDirectedGateway(fixture)
            server, thread, base_url = _start_server(workspace, gateway, fixture)

            def stop_server() -> None:
                server.should_exit = True
                thread.join(timeout=10)
                if thread.is_alive():
                    raise RuntimeError("STEP060 loopback Control API did not stop")

            workspace.register_closer("loopback-control-api", stop_server)
            script = workspace.scratch_dir / "node-cli-script.txt"
            script.write_text("\n".join([REQUEST, "/details", "/quit"]) + "\n", encoding="utf-8")
            result = _run_node(base_url, script)
            transcript = result.stdout + "\n" + result.stderr
            after_files = _files(fixture)
            counts = _counts(
                workspace.database_dir / "product.sqlite3",
                workspace.database_dir / "evaluation.sqlite3",
            )
            product_bytes = (workspace.database_dir / "product.sqlite3").read_bytes()
            after_results = ReferenceCatalogService(ROOT).verify_all()
            after_refs = {item.reference_id: item.actual_tree_sha256 for item in after_results}
            payload_root = workspace.scratch_dir / "protected-payloads"
            payload_count = (
                len([path for path in payload_root.glob("**/*") if path.is_file()])
                if payload_root.exists()
                else 0
            )
            tool_output = gateway.tool_output
            evidence_text = tool_output.model_dump_json() if tool_output is not None else ""
            primary = tool_output.evidence[0] if tool_output is not None else None
            checks = {
                "node_process_exited_successfully": result.returncode == 0,
                "query_directed_tool_executed_once": gateway.calls == 1 and tool_output is not None,
                "korean_query_reduced_to_precise_terms": tool_output is not None and tool_output.query_terms_considered == 2,
                "implementation_registration_ranked_first": primary is not None and primary.path == EXPECTED_PATH,
                "exact_route_and_handler_in_primary_excerpt": primary is not None and '@app.get("/healthz")' in primary.excerpt and "async def health" in primary.excerpt,
                "primary_line_range_contains_registration": primary is not None and primary.line_start <= expected_route_line <= primary.line_end,
                "evidence_file_budget_enforced": tool_output is not None and 1 <= len(tool_output.evidence) <= 4,
                "aggregate_evidence_character_budget_enforced": tool_output is not None and 1 <= tool_output.evidence_characters <= 5_000,
                "per_excerpt_budget_enforced": tool_output is not None and all(len(item.excerpt) <= 1_600 and item.line_end - item.line_start + 1 <= 16 for item in tool_output.evidence),
                "unrelated_docs_and_auth_excluded": tool_output is not None and "docs/plans/legacy-health-api.md" not in tool_output.inspected_files and "okcanvas_agent_runtime/control_api/auth.py" not in tool_output.inspected_files and UNRELATED_SENTINEL not in evidence_text,
                "excluded_dependency_not_read": EXCLUDED_SENTINEL not in evidence_text,
                "direct_answer_contains_exact_relative_evidence": EXPECTED_PATH in transcript and "Health API는" in transcript and str(fixture) not in transcript,
                "narrow_answer_avoids_unrelated_audit": UNRELATED_SENTINEL not in transcript and "distributed worker" not in transcript.lower(),
                "workspace_unchanged": before_files == after_files,
                "raw_request_not_persisted": REQUEST.encode("utf-8") not in product_bytes,
                "tool_result_not_persisted_in_events": '@app.get("/healthz")'.encode("utf-8") not in product_bytes,
                "final_product_counts_exact": counts == {"tasks": 1, "runs": 1, "submissions": 1, "invocations": 1, "events": 12, "artifacts": 1, "evaluations": 0},
                "successful_payload_deleted": payload_count == 0,
                "references_unchanged": before_refs == after_refs and all(item.verified for item in after_results),
                "cleanup_completed": True,
            }
            payload: dict[str, Any] = {
                "schema_version": "okcanvas-step060-acceptance-v1",
                "state": "PASSED" if all(checks.values()) else "FAILED",
                "checks": checks,
                "retrieval": {
                    "query": REQUEST,
                    "query_terms_considered": tool_output.query_terms_considered if tool_output else None,
                    "files_considered": tool_output.files_considered if tool_output else None,
                    "inspected_files": tool_output.inspected_files if tool_output else None,
                    "primary_evidence": (
                        {
                            "path": primary.path,
                            "line_start": primary.line_start,
                            "line_end": primary.line_end,
                        }
                        if primary is not None
                        else None
                    ),
                    "evidence_files": len(tool_output.evidence) if tool_output else None,
                    "evidence_characters": tool_output.evidence_characters if tool_output else None,
                    "max_evidence_files": 4,
                    "max_evidence_characters": 5_000,
                    "max_excerpt_lines": 16,
                    "max_excerpt_characters": 1_600,
                },
                "final_counts": counts,
                "protected_payload_file_count": payload_count,
                "process_returncode": result.returncode,
                "transcript_tail": transcript[-12_000:],
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
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP060_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
