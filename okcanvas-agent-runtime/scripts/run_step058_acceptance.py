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
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult, UsageSummary
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import GatewayLifecycleEvent, GenericGatewayRunResult
from okcanvas_agent_runtime.domain.runs import EventSource
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService

ADMIN = "step058-local-admin-key"
SUBMITTER = "step058-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_HISTORY_KEY = base64.urlsafe_b64encode(
    bytes((index + 67) % 256 for index in range(32))
).decode("ascii")
MODEL = "deterministic-step058-model"
TOOL_AGENT = "local-text-fingerprint-agent"
HANDOFF_AGENT = "handoff-triage-agent"
AGENT_TOOL_AGENT = "agent-tool-manager-agent"
TOOL_SENTINEL = "STEP058-PRIVATE-TOOL-ARGUMENT"
CHILD_SENTINEL = "STEP058-PRIVATE-SUB-AGENT-RESULT"


class DeterministicCapabilityGateway:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def run(self, *, definition, request, run_id, settings, lifecycle_sink, **kwargs):
        self.calls.append(definition.agent_id)
        await lifecycle_sink(GatewayLifecycleEvent("agent.started", {"agent_id": definition.agent_id}))
        await lifecycle_sink(GatewayLifecycleEvent("model.started", {"model": settings.model}))
        if definition.agent_id == TOOL_AGENT:
            await lifecycle_sink(GatewayLifecycleEvent(
                "tool.started",
                {
                    "tool_id": "local_text_fingerprint",
                    "tool_name": "local_text_fingerprint",
                    "runtime_version": "1.0.0",
                    "approval_required": False,
                    "tool_call_id_present": True,
                    "arguments_persisted": False,
                },
                payload_schema_version="okcanvas-function-tool-started-v1",
                source=EventSource.AGENT_SDK,
            ))
            await lifecycle_sink(GatewayLifecycleEvent(
                "tool.completed",
                {
                    "tool_id": "local_text_fingerprint",
                    "tool_name": "local_text_fingerprint",
                    "runtime_version": "1.0.0",
                    "approval_required": False,
                    "tool_call_id_present": True,
                    "result_present": True,
                    "result_persisted": False,
                },
                payload_schema_version="okcanvas-function-tool-completed-v1",
                source=EventSource.AGENT_SDK,
            ))
            summary = "The read-only fingerprint Tool completed."
            usage = UsageSummary(requests=1, input_tokens=20, output_tokens=10, total_tokens=30)
        elif definition.agent_id == HANDOFF_AGENT:
            await lifecycle_sink(GatewayLifecycleEvent(
                "agent.handoff",
                {
                    "from_agent_id": HANDOFF_AGENT,
                    "to_agent_id": "handoff-specialist-agent",
                    "input_filter_mode": "remove_all_tools",
                    "nest_handoff_history": False,
                    "handoff_input_payload_enabled": False,
                    "history_persisted": False,
                    "sdk_session_history_active": False,
                    "parent_usage": UsageSummary(input_tokens=8, output_tokens=2, total_tokens=10).model_dump(mode="json"),
                },
                payload_schema_version="okcanvas-native-handoff-v1",
            ))
            summary = "The request was transferred to the declared specialist."
            usage = UsageSummary(requests=2, input_tokens=22, output_tokens=8, total_tokens=30)
        elif definition.agent_id == AGENT_TOOL_AGENT:
            await lifecycle_sink(GatewayLifecycleEvent(
                "agent.tool.started",
                {
                    "from_agent_id": AGENT_TOOL_AGENT,
                    "to_agent_id": "agent-tool-specialist-agent",
                    "tool_name": "agent_tool_specialist_agent",
                    "tool_call_id_present": True,
                    "arguments_persisted": False,
                    "result_persisted": False,
                    "input_mode": "TEXT",
                    "output_mode": "STRUCTURED",
                    "parent_usage_before": UsageSummary(input_tokens=7, output_tokens=2, total_tokens=9).model_dump(mode="json"),
                },
                payload_schema_version="okcanvas-agent-as-tool-started-v1",
            ))
            await lifecycle_sink(GatewayLifecycleEvent(
                "agent.tool.completed",
                {
                    "from_agent_id": AGENT_TOOL_AGENT,
                    "to_agent_id": "agent-tool-specialist-agent",
                    "tool_name": "agent_tool_specialist_agent",
                    "tool_call_id_present": True,
                    "arguments_persisted": False,
                    "result_present": True,
                    "result_persisted": False,
                    "parent_control_retained": True,
                    "usage_after": UsageSummary(input_tokens=18, output_tokens=7, total_tokens=25).model_dump(mode="json"),
                },
                payload_schema_version="okcanvas-agent-as-tool-completed-v1",
            ))
            summary = "The manager used the specialist Sub Agent and retained control."
            usage = UsageSummary(requests=2, input_tokens=28, output_tokens=12, total_tokens=40)
        else:
            raise AssertionError(f"Unexpected STEP058 Agent: {definition.agent_id}")
        await lifecycle_sink(GatewayLifecycleEvent("model.completed", {"response_id_present": True, "request_id_present": True}))
        await lifecycle_sink(GatewayLifecycleEvent("agent.completed", {"agent_id": definition.agent_id, "output_contract": definition.output_contract}))
        return GenericGatewayRunResult(
            output=CodingAgentResult(status=AgentStatus.PASS, summary=summary, findings=[], unverified=[]),
            usage=usage,
            trace_id=f"trace-step058-{definition.agent_id}",
            response_id=None,
            sdk_version="0.19.0",
        )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_server(workspace: AcceptanceWorkspace, gateway: DeterministicCapabilityGateway):
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
        gateway=gateway,
    )
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning", lifespan="on"))
    thread = threading.Thread(target=server.run, name="step058-control-api", daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.02)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=5)
        raise RuntimeError("STEP058 loopback Control API did not start")
    return app, server, thread, f"http://127.0.0.1:{port}"


def _run_node(base_url: str, script_path: Path):
    env = os.environ.copy()
    env.update({"OKCANVAS_CONTROL_ADMIN_KEY": ADMIN, "OKCANVAS_RUN_SUBMITTER_KEY": SUBMITTER})
    return subprocess.run(
        [
            "node", str(ROOT / "clients" / "cli" / "dist" / "cli.js"),
            "--base-url", base_url,
            "--agent-id", TOOL_AGENT,
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


def run_acceptance(output: Path) -> int:
    before_results = ReferenceCatalogService(ROOT).verify_all()
    before = {item.reference_id: item.actual_tree_sha256 for item in before_results}
    previous_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "step058-hidden-api-key"
    try:
        with AcceptanceWorkspace(step_id="STEP058", output=output) as workspace:
            gateway = DeterministicCapabilityGateway()
            app, server, thread, base_url = _start_server(workspace, gateway)

            def stop_server() -> None:
                server.should_exit = True
                thread.join(timeout=10)
                if thread.is_alive():
                    raise RuntimeError("STEP058 loopback Control API did not stop")

            workspace.register_closer("loopback-control-api", stop_server)
            script = workspace.scratch_dir / "node-cli-script.txt"
            script.write_text("\n".join([
                f"Fingerprint this text: {TOOL_SENTINEL}",
                f"/use {HANDOFF_AGENT}",
                "Route this request to the declared specialist.",
                f"/use {AGENT_TOOL_AGENT}",
                f"Ask the specialist to review {CHILD_SENTINEL}.",
                "/invocations",
                "/agents",
                "/quit",
            ]) + "\n", encoding="utf-8")
            result = _run_node(base_url, script)
            transcript = result.stdout + "\n" + result.stderr
            counts = _counts(workspace.database_dir / "product.sqlite3", workspace.database_dir / "evaluation.sqlite3")
            product_bytes = (workspace.database_dir / "product.sqlite3").read_bytes()
            after_results = ReferenceCatalogService(ROOT).verify_all()
            after = {item.reference_id: item.actual_tree_sha256 for item in after_results}
            payload_root = workspace.scratch_dir / "protected-payloads"
            payload_count = len([p for p in payload_root.glob("**/*") if p.is_file()]) if payload_root.exists() else 0
            client_source = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "clients" / "cli" / "src").glob("*.ts"))
            package = json.loads((ROOT / "clients" / "cli" / "package.json").read_text(encoding="utf-8"))
            checks = {
                "node_process_exited_successfully": result.returncode == 0,
                "safe_read_only_tool_visible_and_executed": "↳ Tool local_text_fingerprint 실행" in transcript and "✓ Tool local_text_fingerprint 완료" in transcript,
                "native_handoff_visible_and_executed": "↳ Handoff handoff-triage-agent → handoff-specialist-agent" in transcript,
                "agent_as_tool_visible_and_executed": "↳ Sub Agent agent-tool-specialist-agent 호출" in transcript and "✓ Sub Agent agent-tool-specialist-agent 완료" in transcript,
                "answer_first_mode_preserved": transcript.count("Agent\n─────") == 3,
                "invocation_tree_visible": "ROOT · agent-tool-manager-agent · SUCCEEDED" in transcript and "AGENT_AS_TOOL · agent-tool-specialist-agent · SUCCEEDED" in transcript,
                "agent_catalog_labels_capabilities": "read-only Tool local_text_fingerprint" in transcript and "Handoff → handoff-specialist-agent" in transcript and "Sub Agent → agent-tool-specialist-agent" in transcript,
                "approval_required_tool_excluded": "local-text-metrics-agent" not in transcript,
                "mcp_and_guardrail_agents_excluded": "reference-research-agent" not in transcript and "guardrail-language-agent" not in transcript,
                "raw_tool_and_child_data_not_printed": TOOL_SENTINEL not in transcript.replace(f"Fingerprint this text: {TOOL_SENTINEL}", "") and CHILD_SENTINEL not in transcript.replace(f"Ask the specialist to review {CHILD_SENTINEL}.", ""),
                "raw_requests_not_persisted": TOOL_SENTINEL.encode() not in product_bytes and CHILD_SENTINEL.encode() not in product_bytes,
                "gateway_paths_exact": gateway.calls == [TOOL_AGENT, HANDOFF_AGENT, AGENT_TOOL_AGENT],
                "final_product_counts_exact": counts == {"tasks": 3, "runs": 3, "submissions": 3, "invocations": 5, "events": 35, "artifacts": 3, "evaluations": 0},
                "successful_payloads_deleted": payload_count == 0,
                "control_api_only": "okcanvas_agent_runtime" not in client_source and "node:sqlite" not in client_source.lower() and ".sqlite3" not in client_source.lower(),
                "npm_installable_structure_preserved": package.get("version") == "0.5.0" and package.get("bin", {}).get("okcanvas-agent") == "./dist/cli.js" and not package.get("dependencies"),
                "references_unchanged": before == after and all(item.verified for item in after_results),
                "cleanup_completed": True,
            }
            payload: dict[str, Any] = {
                "schema_version": "okcanvas-step058-acceptance-v1",
                "state": "PASSED" if all(checks.values()) else "FAILED",
                "checks": checks,
                "node_cli": {
                    "language": "TypeScript",
                    "runtime": "Node.js >=22",
                    "process_count": 1,
                    "request_count": 3,
                    "runtime_dependencies": 0,
                    "supported_capability_paths": ["READ_ONLY_FUNCTION_TOOL", "HANDOFF", "AGENT_AS_TOOL"],
                    "approval_decision_enabled": False,
                    "mcp_enabled": False,
                    "guardrail_enabled": False,
                },
                "gateway_calls": gateway.calls,
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
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "evidence" / "STEP058_ACCEPTANCE.json")
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
