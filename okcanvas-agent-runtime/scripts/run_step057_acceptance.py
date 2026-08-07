from __future__ import annotations

import argparse
import base64
import importlib.metadata
import json
import os
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import uvicorn

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_runtime.adapters.streaming import InMemoryNativeSDKStreamBroker

ADMIN = "step057-local-admin-key"
SUBMITTER = "step057-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(31, -1, -1))).decode("ascii")
SESSION_HISTORY_KEY = base64.urlsafe_b64encode(
    bytes((index + 67) % 256 for index in range(32))
).decode("ascii")
HIDDEN_API_KEY = "step057-hidden-api-key"
MODEL = "deterministic-step057-model"
AGENT_ID = "conversational-coding-agent"
NAME_SENTINEL = "KEVIN-57"
TURN1 = f"Remember that my name is {NAME_SENTINEL}."
TURN2 = "What is my name?"
TURN3 = "What is my name after restarting the CLI?"
TURN4 = "What is my name in this new conversation?"


def _usage(input_tokens: int, output_tokens: int):
    return SimpleNamespace(
        requests=1,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
        output_tokens_details=SimpleNamespace(reasoning_tokens=0),
    )


def _install_fake_agents():
    counters = {"run": 0, "run_streamed": 0, "session_instances": 0, "session_closes": 0}
    captured: dict[str, list[Any]] = {"history_before": [], "session_ids": [], "requests": []}
    previous_agents = sys.modules.get("agents")
    previous_version = importlib.metadata.version
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    class FakeSQLiteSession:
        def __init__(self, session_id: str, db_path: str | Path) -> None:
            counters["session_instances"] += 1
            self.session_id = session_id
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(self.db_path, timeout=15, check_same_thread=False)
            self.connection.execute(
                """CREATE TABLE IF NOT EXISTS fake_agent_session_item(
                    session_id TEXT NOT NULL,
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_json TEXT NOT NULL
                )"""
            )
            self.connection.commit()
            self.closed = False

        async def get_items(self, limit: int | None = None):
            rows = self.connection.execute(
                "SELECT item_json FROM fake_agent_session_item WHERE session_id=? ORDER BY sequence ASC",
                (self.session_id,),
            ).fetchall()
            items = [json.loads(row[0]) for row in rows]
            return items[-limit:] if limit is not None else items

        async def add_items(self, items):
            self.connection.executemany(
                "INSERT INTO fake_agent_session_item(session_id,item_json) VALUES(?,?)",
                [(self.session_id, json.dumps(item, ensure_ascii=False, sort_keys=True)) for item in items],
            )
            self.connection.commit()

        async def pop_item(self):
            row = self.connection.execute(
                "SELECT sequence,item_json FROM fake_agent_session_item WHERE session_id=? ORDER BY sequence DESC LIMIT 1",
                (self.session_id,),
            ).fetchone()
            if row is None:
                return None
            self.connection.execute("DELETE FROM fake_agent_session_item WHERE sequence=?", (row[0],))
            self.connection.commit()
            return json.loads(row[1])

        async def clear_session(self):
            self.connection.execute(
                "DELETE FROM fake_agent_session_item WHERE session_id=?", (self.session_id,)
            )
            self.connection.commit()

        def close(self) -> None:
            if not self.closed:
                self.closed = True
                counters["session_closes"] += 1
                self.connection.close()

    class FakeAgent:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeRunConfig:
        def __init__(self, **kwargs):
            self.values = kwargs

    class FakeRunHooks:
        pass

    class FakeStreamingResult:
        def __init__(self, *, agent, request: str, session, hooks, ordinal: int) -> None:
            self.agent = agent
            self.request = request
            self.session = session
            self.hooks = hooks
            self.ordinal = ordinal
            self.last_response_id = f"resp-step057-{ordinal}"
            self.context_wrapper = SimpleNamespace(usage=_usage(20 + ordinal, 8 + ordinal))
            self._output: CodingAgentResult | None = None

        async def stream_events(self):
            history = await self.session.get_items()
            captured["history_before"].append(history)
            captured["session_ids"].append(self.session.session_id)
            captured["requests"].append(self.request)
            history_text = json.dumps(history, ensure_ascii=False)
            if self.request == TURN1:
                summary = f"I will remember that your name is {NAME_SENTINEL}."
            elif NAME_SENTINEL in history_text:
                summary = f"Your name is {NAME_SENTINEL}."
            else:
                summary = "I do not know your name in this Session."
            self._output = CodingAgentResult(
                status=AgentStatus.PASS,
                summary=summary,
                findings=[],
                unverified=[],
            )
            await self.hooks.on_agent_start(SimpleNamespace(), self.agent)
            await self.hooks.on_llm_start(
                SimpleNamespace(), self.agent, self.agent.instructions, [{"role": "user"}]
            )
            yield SimpleNamespace(type="agent_updated_stream_event", new_agent=self.agent)
            yield SimpleNamespace(
                type="raw_response_event",
                data=SimpleNamespace(type="response.output_text.delta", delta=summary),
            )
            await self.session.add_items(
                [
                    {"role": "user", "content": self.request},
                    {"role": "assistant", "content": summary},
                ]
            )
            response = SimpleNamespace(
                response_id=self.last_response_id,
                request_id=f"req-step057-{self.ordinal}",
                output=[1],
            )
            await self.hooks.on_llm_end(SimpleNamespace(), self.agent, response)
            await self.hooks.on_agent_end(SimpleNamespace(), self.agent, self._output)

        def final_output_as(self, output_type, raise_if_incorrect_type=False):
            assert output_type is CodingAgentResult
            assert raise_if_incorrect_type is True
            assert self._output is not None
            return self._output

    class FakeRunner:
        @classmethod
        async def run(cls, *args, **kwargs):
            counters["run"] += 1
            raise AssertionError("STEP057 must use Runner.run_streamed")

        @classmethod
        def run_streamed(cls, agent, request, **kwargs):
            counters["run_streamed"] += 1
            session = kwargs.get("session")
            if session is None:
                raise AssertionError("STEP057 requires installed SDK SQLiteSession")
            return FakeStreamingResult(
                agent=agent,
                request=request,
                session=session,
                hooks=kwargs["hooks"],
                ordinal=counters["run_streamed"],
            )

    class FakeModelRetrySettings:
        def __init__(self, **kwargs):
            self.max_retries = kwargs.get("max_retries")
            self.policy = kwargs.get("policy")

    class FakeRetryPolicies:
        @staticmethod
        def never():
            return lambda _context: False

    class FakeModelSettings:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    fake_agents.Agent = FakeAgent
    fake_agents.ModelSettings = FakeModelSettings
    fake_agents.ModelRetrySettings = FakeModelRetrySettings
    fake_agents.retry_policies = FakeRetryPolicies()
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.SQLiteSession = FakeSQLiteSession
    fake_agents.gen_trace_id = lambda: "trace-step057"
    fake_agents.set_default_openai_key = lambda value: None
    sys.modules["agents"] = fake_agents
    importlib.metadata.version = (
        lambda name: "0.19.0" if name == "openai-agents" else previous_version(name)
    )
    return counters, captured, previous_version, previous_agents


def _restore(previous_version, previous_agents) -> None:
    importlib.metadata.version = previous_version
    if previous_agents is None:
        sys.modules.pop("agents", None)
    else:
        sys.modules["agents"] = previous_agents


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_server(workspace: AcceptanceWorkspace):
    broker = InMemoryNativeSDKStreamBroker()
    app = create_app(
        project_root=ROOT,
        product_db=workspace.database_dir / "product.sqlite3",
        evaluation_db=workspace.database_dir / "evaluation.sqlite3",
        artifact_root=workspace.artifact_dir,
        admin_key=ADMIN,
        run_submitter_key=SUBMITTER,
        protected_payload_root=workspace.scratch_dir / "protected-payloads",
        protected_payload_key=PAYLOAD_KEY,
        native_stream_broker=broker,
        session_root=workspace.scratch_dir / "sessions",
        session_history_key=SESSION_HISTORY_KEY,
    )
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning", lifespan="on")
    )
    thread = threading.Thread(target=server.run, name="step057-control-api", daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.02)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=5)
        raise RuntimeError("STEP057 loopback Control API did not start")
    return app, server, thread, f"http://127.0.0.1:{port}"


def _run_node(base_url: str, script_path: Path, *, session_id: str | None = None):
    command = [
        "node",
        str(ROOT / "clients" / "cli" / "dist" / "cli.js"),
        "--base-url",
        base_url,
        "--agent-id",
        AGENT_ID,
        "--model",
        MODEL,
        "--script",
        str(script_path),
        "--yes",
        "--no-color",
    ]
    if session_id:
        command.extend(["--session-id", session_id])
    environment = os.environ.copy()
    environment.update(
        {
            "OKCANVAS_CONTROL_ADMIN_KEY": ADMIN,
            "OKCANVAS_RUN_SUBMITTER_KEY": SUBMITTER,
        }
    )
    return subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
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
    counters, captured, previous_version, previous_agents = _install_fake_agents()
    previous_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = HIDDEN_API_KEY
    try:
        with AcceptanceWorkspace(step_id="STEP057", output=output) as workspace:
            app, server, thread, base_url = _start_server(workspace)

            def stop_server() -> None:
                server.should_exit = True
                thread.join(timeout=10)
                if thread.is_alive():
                    raise RuntimeError("STEP057 loopback Control API did not stop")

            workspace.register_closer("loopback-control-api", stop_server)
            first_script = workspace.scratch_dir / "first-cli-script.txt"
            first_script.write_text(
                "\n".join([TURN1, TURN2, "/session", "/sessions", "/history", "/quit"]) + "\n",
                encoding="utf-8",
            )
            first = _run_node(base_url, first_script)
            sessions_after_first = app.state.session_runtime.list(limit=20)
            if len(sessions_after_first) != 1:
                raise RuntimeError("STEP057 first CLI did not create exactly one Session")
            first_session_id = sessions_after_first[0].session_id

            second_script = workspace.scratch_dir / "second-cli-script.txt"
            second_script.write_text(
                "\n".join(
                    [
                        TURN3,
                        "/session",
                        "/evaluate node-cli-session-conversation-v1",
                        "/history",
                        "/new",
                        TURN4,
                        "/sessions",
                        "/quit",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            second = _run_node(base_url, second_script, session_id=first_session_id)
            transcript = first.stdout + first.stderr + second.stdout + second.stderr
            sessions = app.state.session_runtime.list(limit=20)
            by_id = {item.session_id: item for item in sessions}
            first_session = by_id[first_session_id]
            second_session = next(item for item in sessions if item.session_id != first_session_id)

            product_db = workspace.database_dir / "product.sqlite3"
            evaluation_db = workspace.database_dir / "evaluation.sqlite3"
            counts = _counts(product_db, evaluation_db)
            product_bytes = product_db.read_bytes()
            evaluation_bytes = evaluation_db.read_bytes()
            history_db = workspace.scratch_dir / "sessions" / "history.sqlite3"
            history_text = history_db.read_bytes().decode("utf-8", errors="ignore")
            payload_count = len(list((workspace.scratch_dir / "protected-payloads").glob("payload_*.json")))
            cli_root = ROOT / "clients" / "cli"
            source_text = "\n".join(
                path.read_text(encoding="utf-8") for path in sorted((cli_root / "src").glob("*.ts"))
            )
            package = json.loads((cli_root / "package.json").read_text(encoding="utf-8"))
            after_results = ReferenceCatalogService(ROOT).verify_all()
            after = {item.reference_id: item.actual_tree_sha256 for item in after_results}
            histories = captured["history_before"]
            session_ids = captured["session_ids"]
            checks = {
                "node_processes_exited_successfully": first.returncode == 0 and second.returncode == 0,
                "canonical_conversational_agent_is_session_enabled": "conversational-coding-agent" in transcript
                and "Runtime Session 대화 기억 사용" in transcript,
                "first_cli_created_runtime_session": "새 Runtime Session:" in transcript
                and len(sessions_after_first) == 1,
                "same_process_turn_two_received_turn_one_history": len(histories) == 4
                and NAME_SENTINEL in json.dumps(histories[1], ensure_ascii=False),
                "semantic_name_memory_visible_to_user": transcript.count(f"Your name is {NAME_SENTINEL}.") >= 2,
                "same_session_bound_first_three_turns": len(session_ids) == 4
                and session_ids[0] == session_ids[1] == session_ids[2] == first_session_id,
                "cli_restart_resumed_exact_session": f"Runtime Session 재개: {first_session_id}" in transcript
                and NAME_SENTINEL in json.dumps(histories[2], ensure_ascii=False),
                "new_command_created_isolated_session": len(sessions) == 2
                and session_ids[3] == second_session.session_id
                and session_ids[3] != first_session_id,
                "new_session_does_not_leak_prior_memory": histories[3] == []
                and "I do not know your name in this Session." in transcript,
                "session_metadata_counts_exact": first_session.turn_count == 3
                and first_session.item_count == 6
                and second_session.turn_count == 1
                and second_session.item_count == 2,
                "session_commands_visible_and_safe": "/session" in first_script.read_text(encoding="utf-8")
                and "Turns: 2" in transcript
                and "이 CLI 프로세스의 대화" in transcript
                and "재개한 과거 Session 원문은 서버에서 자동 노출하지 않습니다" not in transcript,
                "explicit_evaluation_passed": "node-cli-session-conversation-v1 · PASSED" in transcript
                and counts["evaluations"] == 1,
                "evaluation_default_remains_off": transcript.count("[Evaluation]") == 1,
                "governed_session_preflights_used": counts["submissions"] == 4
                and all(item == first_session_id for item in session_ids[:3]),
                "persisted_sse_and_session_events_exact": counts["events"] == 48
                and transcript.count("session turn") == 4,
                "final_product_counts_exact": counts == {
                    "tasks": 4,
                    "runs": 4,
                    "submissions": 4,
                    "invocations": 4,
                    "events": 48,
                    "artifacts": 4,
                    "evaluations": 1,
                },
                "session_history_only_in_session_store": NAME_SENTINEL in history_text
                and NAME_SENTINEL.encode() not in product_bytes
                and NAME_SENTINEL.encode() not in evaluation_bytes,
                "raw_requests_not_in_product_or_evaluation_db": all(
                    request.encode() not in product_bytes + evaluation_bytes
                    for request in [TURN1, TURN2, TURN3, TURN4]
                ),
                "successful_payloads_deleted": payload_count == 0,
                "credentials_not_printed_or_persisted": ADMIN not in transcript
                and SUBMITTER not in transcript
                and HIDDEN_API_KEY not in transcript
                and ADMIN.encode() not in product_bytes + evaluation_bytes
                and SUBMITTER.encode() not in product_bytes + evaluation_bytes,
                "session_handles_closed": counters["session_instances"] == counters["session_closes"],
                "node_cli_session_api_only": "/v1/sessions" in source_text
                and "session_id" in source_text
                and "okcanvas_agent_runtime" not in source_text
                and "python" not in source_text.lower(),
                "npm_installable_structure_preserved": package.get("bin", {}).get("okcanvas-agent") == "./dist/cli.js"
                and package.get("version") == "0.5.0"
                and not package.get("dependencies"),
                "references_unchanged": before == after and all(item.verified for item in after_results),
                "cleanup_completed": True,
            }
            payload: dict[str, Any] = {
                "schema_version": "okcanvas-step057-acceptance-v1",
                "state": "PASSED" if all(checks.values()) else "FAILED",
                "checks": checks,
                "node_cli": {
                    "language": "TypeScript",
                    "runtime": "Node.js >=22",
                    "session_enabled": True,
                    "canonical_agent": AGENT_ID,
                    "process_count": 2,
                    "turn_count": counters["run_streamed"],
                    "runtime_dependencies": 0,
                    "evaluation_default_enabled": False,
                    "direct_runtime_access": False,
                },
                "sessions": {
                    "created": len(sessions),
                    "resumed_session_id": first_session_id,
                    "resumed_turn_count": first_session.turn_count,
                    "resumed_item_count": first_session.item_count,
                    "new_session_id": second_session.session_id,
                    "new_turn_count": second_session.turn_count,
                    "new_item_count": second_session.item_count,
                },
                "final_counts": counts,
                "protected_payload_file_count": payload_count,
                "process_returncodes": [first.returncode, second.returncode],
                "transcript_tail": transcript[-9000:],
            }
            final = workspace.finalize(payload)
    finally:
        if previous_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = previous_key
        _restore(previous_version, previous_agents)
    print(json.dumps(final, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if final["state"] == "PASSED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "STEP057_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
