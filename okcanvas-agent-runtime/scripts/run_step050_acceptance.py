from __future__ import annotations

import argparse
import asyncio
import base64
import importlib.metadata
import json
import os
import sqlite3
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.application.execution import openai_gateway as gateway_module
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_runtime.domain.sessions import SessionBusyError, StrictEncryptedSession
from okcanvas_agent_runtime.adapters.streaming import InMemoryNativeSDKStreamBroker

ADMIN_KEY = "step050-local-admin-key"
SUBMITTER_KEY = "step050-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
SESSION_HISTORY_KEY = base64.urlsafe_b64encode(
    bytes((index + 67) % 256 for index in range(32))
).decode("ascii")
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SUBMIT_HEADERS = {**ADMIN_HEADERS, "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY}
AGENT_ID = "session-reference-research-agent"
MARKER = "COMET-50"
FAIL_SENTINEL = "FAIL-MCP-50"
RAW_QUERY_SENTINEL = "STEP050-RAW-MCP-QUERY-MUST-NOT-ENTER-PRODUCT"
RAW_RESULT_SENTINEL = "STEP050-RAW-MCP-RESULT-MUST-NOT-ENTER-PRODUCT"
HIDDEN_API_KEY = "step050-hidden-api-key"
REQUESTS = {
    "clean_1": f"Use the declared MCP server and remember Session marker {MARKER}.",
    "mcp_failure": f"Use the declared MCP server then trigger {FAIL_SENTINEL}; this Turn must roll back.",
    "clean_2": "Use the declared MCP server again and report the marker from the prior committed Turn.",
}


def _usage(input_tokens: int, output_tokens: int):
    return SimpleNamespace(
        requests=1,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
        output_tokens_details=SimpleNamespace(reasoning_tokens=0),
    )


def _install_fakes():
    counters = {
        "run": 0,
        "run_streamed": 0,
        "model_calls": 0,
        "mcp_runtime_created": 0,
        "mcp_manager_enters": 0,
        "mcp_manager_exits": 0,
        "mcp_tool_calls": 0,
        "session_instances": 0,
        "session_closes": 0,
    }
    captured: dict[str, object] = {
        "history_before": [],
        "session_ids": [],
        "manager_server_names": [],
        "manager_order": [],
        "agent_mcp_server_names": [],
        "active_turn_index": 0,
    }
    previous_modules = {"agents": sys.modules.get("agents"), "openai": sys.modules.get("openai")}
    previous_version = importlib.metadata.version
    previous_factory = gateway_module.create_openai_mcp_runtime
    fake_agents = types.ModuleType("agents")
    fake_openai = types.ModuleType("openai")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            self.kwargs = dict(kwargs)

    class FakeOpenAIProvider:
        def __init__(self, **kwargs):
            self.kwargs = dict(kwargs)
            self.closed = False

        def get_model(self, model_name):
            return SimpleNamespace(model_name=model_name)

        async def aclose(self):
            self.closed = True

    class FakeModelSettings:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeModelRetrySettings:
        def __init__(self, **kwargs):
            self.max_retries = kwargs.get("max_retries")
            self.policy = kwargs.get("policy")

    class FakeRetryPolicies:
        @staticmethod
        def never():
            return lambda _context: False

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
            captured["manager_order"].append(
                f"rollback_pop_{captured['active_turn_index']}"
            )
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

    class FakeServer:
        name = "reference-catalog"

    class FakeManager:
        def __init__(self, index: int) -> None:
            self.index = index
            self.active_servers = [FakeServer()]

        async def __aenter__(self):
            counters["mcp_manager_enters"] += 1
            captured["manager_server_names"].append(
                [server.name for server in self.active_servers]
            )
            captured["manager_order"].append(f"manager_enter_{self.index}")
            return self

        async def __aexit__(self, exc_type, exc, tb):
            counters["mcp_manager_exits"] += 1
            captured["manager_order"].append(f"manager_exit_{self.index}")
            return False

    def fake_mcp_runtime(definitions, *, project_root):
        counters["mcp_runtime_created"] += 1
        index = counters["mcp_runtime_created"]
        assert len(definitions) == 1
        assert definitions[0].server_id == "reference-catalog"
        return SimpleNamespace(manager=FakeManager(index))

    class FakeRunConfig:
        def __init__(self, **kwargs):
            self.values = kwargs

    class FakeRunHooks:
        pass

    class FakeAgent:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
            captured["agent_mcp_server_names"].append(
                [server.name for server in kwargs.get("mcp_servers", [])]
            )

    class FakeStreamingResult:
        def __init__(self, *, agent, request: str, session, hooks, turn_index: int) -> None:
            self.agent = agent
            self.request = request
            self.session = session
            self.hooks = hooks
            self.turn_index = turn_index
            self.last_response_id = f"resp-step050-{turn_index}"
            self.context_wrapper = SimpleNamespace(usage=_usage(20 + turn_index, 8))
            self._output: CodingAgentResult | None = None

        async def stream_events(self):
            captured["active_turn_index"] = self.turn_index
            history = await self.session.get_items()
            captured["history_before"].append(history)
            captured["session_ids"].append(self.session.session_id)
            await self.hooks.on_agent_start(SimpleNamespace(), self.agent)
            await self.hooks.on_llm_start(
                SimpleNamespace(), self.agent, self.agent.instructions, [{"role": "user"}]
            )
            counters["model_calls"] += 1
            tool = SimpleNamespace(
                name="search_reference",
                _tool_origin=SimpleNamespace(mcp_server_name="reference-catalog"),
            )
            context = SimpleNamespace(
                tool_name="search_reference",
                tool_call_id=f"secret-call-{self.turn_index}",
                tool_arguments=json.dumps({"query": RAW_QUERY_SENTINEL}),
            )
            await self.hooks.on_tool_start(context, self.agent, tool)
            counters["mcp_tool_calls"] += 1
            await self.hooks.on_tool_end(context, self.agent, tool, RAW_RESULT_SENTINEL)

            if FAIL_SENTINEL in self.request:
                await self.session.add_items(
                    [
                        {"role": "user", "content": self.request},
                        {"role": "assistant", "tool_call": "search_reference"},
                        {"role": "tool", "content": RAW_RESULT_SENTINEL},
                    ]
                )
                raise RuntimeError("deterministic MCP failure after partial Session persistence")

            if self.turn_index == 1:
                summary = f"Read-only MCP completed and committed Session marker {MARKER}."
            else:
                history_text = json.dumps(history, ensure_ascii=False)
                if MARKER not in history_text or FAIL_SENTINEL in history_text:
                    raise AssertionError("Later MCP Turn received incorrect committed Session history")
                summary = f"Read-only MCP continuity confirmed marker {MARKER}."
            self._output = CodingAgentResult(
                status=AgentStatus.PASS,
                summary=summary,
                findings=[],
                unverified=[],
            )
            await self.session.add_items(
                [
                    {"role": "user", "content": self.request},
                    {"role": "assistant", "tool_call": "search_reference"},
                    {"role": "tool", "content": RAW_RESULT_SENTINEL},
                    {"role": "assistant", "content": summary},
                ]
            )
            usage = self.context_wrapper.usage
            await self.hooks.on_llm_end(
                SimpleNamespace(usage=usage),
                self.agent,
                SimpleNamespace(response_id=self.last_response_id, request_id="req", output=[1]),
            )
            await self.hooks.on_agent_end(SimpleNamespace(usage=usage), self.agent, self._output)
            yield SimpleNamespace(type="agent_updated_stream_event", new_agent=self.agent)
            yield SimpleNamespace(
                type="raw_response_event",
                data=SimpleNamespace(type="response.output_text.delta", delta=summary),
            )

        def final_output_as(self, output_type, raise_if_incorrect_type=False):
            assert output_type is CodingAgentResult
            assert raise_if_incorrect_type is True
            assert self._output is not None
            return self._output

    class FakeRunner:
        @classmethod
        async def run(cls, agent, request, **kwargs):
            counters["run"] += 1
            raise AssertionError("STEP050 must use Runner.run_streamed")

        @classmethod
        def run_streamed(cls, agent, request, **kwargs):
            counters["run_streamed"] += 1
            if kwargs.get("session") is None:
                raise AssertionError("STEP050 requires installed SDK SQLiteSession")
            return FakeStreamingResult(
                agent=agent,
                request=request,
                session=kwargs["session"],
                hooks=kwargs["hooks"],
                turn_index=counters["run_streamed"],
            )

    fake_agents.Agent = FakeAgent
    fake_agents.ModelSettings = FakeModelSettings
    fake_agents.ModelRetrySettings = FakeModelRetrySettings
    fake_agents.retry_policies = FakeRetryPolicies()
    fake_agents.OpenAIProvider = FakeOpenAIProvider
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.SQLiteSession = FakeSQLiteSession
    fake_agents.gen_trace_id = lambda: "trace_step050"
    fake_agents.set_default_openai_key = lambda key: None
    fake_openai.AsyncOpenAI = FakeAsyncOpenAI
    sys.modules["agents"] = fake_agents
    sys.modules["openai"] = fake_openai
    importlib.metadata.version = (
        lambda name: "0.19.0" if name == "openai-agents" else previous_version(name)
    )
    gateway_module.create_openai_mcp_runtime = fake_mcp_runtime
    return counters, captured, previous_version, previous_modules, previous_factory


def _restore(previous_version, previous_modules, previous_factory):
    importlib.metadata.version = previous_version
    gateway_module.create_openai_mcp_runtime = previous_factory
    for name, module in previous_modules.items():
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


def _wait_terminal(client: TestClient, run_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        body = client.get(f"/v1/runs/{run_id}", headers=ADMIN_HEADERS).json()
        if body.get("status") in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return body
        time.sleep(0.02)
    raise RuntimeError("STEP050 Run did not terminate")


def _execute(client: TestClient, *, session_id: str, request: str, key: str):
    preflight_response = client.post(
        "/v1/run-submissions/preflight",
        headers=SUBMIT_HEADERS,
        json={
            "agent_definition_id": AGENT_ID,
            "session_id": session_id,
            "input": request,
            "model": "deterministic-step050-model",
            "idempotency_key": key,
        },
    )
    preflight = preflight_response.json()
    if preflight_response.status_code != 201:
        raise RuntimeError(f"STEP050 preflight failed: {preflight_response.status_code} {preflight!r}")
    confirm_response = client.post(
        f"/v1/run-submissions/{preflight['submission_id']}/confirm",
        headers=SUBMIT_HEADERS,
        json={"confirmation": preflight["confirmation_challenge"]},
    )
    confirmed = confirm_response.json()
    if "run_id" not in confirmed:
        raise RuntimeError(f"STEP050 confirmation failed: {confirm_response.status_code} {confirmed!r}")
    terminal = _wait_terminal(client, confirmed["run_id"])
    events = client.get(
        f"/v1/runs/{confirmed['run_id']}/events", headers=ADMIN_HEADERS
    ).json()["events"]
    invocations = client.get(
        f"/v1/runs/{confirmed['run_id']}/invocations", headers=ADMIN_HEADERS
    ).json()["invocations"]
    submission = client.get(
        f"/v1/run-submissions/{preflight['submission_id']}", headers=ADMIN_HEADERS
    ).json()
    return {
        "preflight": preflight,
        "confirmed": confirmed,
        "terminal": terminal,
        "events": events,
        "invocations": invocations,
        "submission": submission,
    }


def _counts(product_db: Path, evaluation_db: Path) -> dict[str, int]:
    product = sqlite3.connect(product_db)
    evaluation = sqlite3.connect(evaluation_db)
    try:
        return {
            "tasks": product.execute("select count(*) from task").fetchone()[0],
            "runs": product.execute("select count(*) from run").fetchone()[0],
            "submissions": product.execute("select count(*) from run_submission_preflight").fetchone()[0],
            "invocations": product.execute("select count(*) from agent_invocation").fetchone()[0],
            "events": product.execute("select count(*) from run_event").fetchone()[0],
            "artifacts": product.execute("select count(*) from artifact").fetchone()[0],
            "evaluations": evaluation.execute("select count(*) from evaluation_result").fetchone()[0],
        }
    finally:
        product.close()
        evaluation.close()


def _history_items(runtime, session_id: str) -> list[dict[str, object]]:
    connection = sqlite3.connect(runtime.history_db)
    try:
        encrypted_items = [
            json.loads(row[0])
            for row in connection.execute(
                "SELECT item_json FROM fake_agent_session_item WHERE session_id=? ORDER BY sequence",
                (session_id,),
            ).fetchall()
        ]
    finally:
        connection.close()

    class CapturedSession:
        async def get_items(self, limit: int | None = None):
            return encrypted_items[-limit:] if limit is not None else list(encrypted_items)

    assert runtime.history_key is not None
    encrypted_session = StrictEncryptedSession(
        session_id=session_id, underlying_session=CapturedSession(), key=runtime.history_key
    )
    return asyncio.run(encrypted_session.get_items())


def run_acceptance(output: Path) -> int:
    references_before = {
        item.reference_id: item.to_dict() for item in ReferenceCatalogService(ROOT).verify_all()
    }
    counters, captured, previous_version, previous_modules, previous_factory = _install_fakes()
    previous_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = HIDDEN_API_KEY
    try:
        with AcceptanceWorkspace(step_id="STEP050", output=output) as workspace:
            product_db = workspace.database_dir / "product.sqlite3"
            evaluation_db = workspace.database_dir / "evaluation.sqlite3"
            session_root = workspace.scratch_dir / "sessions"
            payload_root = workspace.scratch_dir / "protected-payloads"
            app = create_app(
                project_root=ROOT,
                product_db=product_db,
                artifact_root=workspace.artifact_dir,
                evaluation_db=evaluation_db,
                admin_key=ADMIN_KEY,
                run_submitter_key=SUBMITTER_KEY,
                protected_payload_root=payload_root,
                protected_payload_key=PAYLOAD_KEY,
                native_stream_broker=InMemoryNativeSDKStreamBroker(),
                session_root=session_root,
                session_history_key=SESSION_HISTORY_KEY,
            )
            with TestClient(app) as client:
                unauthenticated = client.get("/v1/sessions")
                create_response = client.post(
                    "/v1/sessions",
                    headers=SUBMIT_HEADERS,
                    json={"agent_definition_id": AGENT_ID},
                )
                created = create_response.json()
                if create_response.status_code != 201:
                    raise RuntimeError(f"STEP050 Session create failed: {create_response.status_code} {created!r}")
                session_id = created["session_id"]

                clean_1 = _execute(
                    client,
                    session_id=session_id,
                    request=REQUESTS["clean_1"],
                    key="step050-clean-0001",
                )
                after_clean_1 = client.get(
                    f"/v1/sessions/{session_id}", headers=ADMIN_HEADERS
                ).json()
                failed = _execute(
                    client,
                    session_id=session_id,
                    request=REQUESTS["mcp_failure"],
                    key="step050-mcp-failure-0002",
                )
                after_failure = client.get(
                    f"/v1/sessions/{session_id}", headers=ADMIN_HEADERS
                ).json()
                clean_2 = _execute(
                    client,
                    session_id=session_id,
                    request=REQUESTS["clean_2"],
                    key="step050-clean-0003",
                )
                after_clean_2 = client.get(
                    f"/v1/sessions/{session_id}", headers=ADMIN_HEADERS
                ).json()

                artifact2 = client.get(
                    f"/v1/runs/{clean_2['confirmed']['run_id']}/artifact",
                    headers=ADMIN_HEADERS,
                ).json()
                evaluation_response = client.post(
                    f"/v1/runs/{clean_2['confirmed']['run_id']}/evaluations",
                    headers=ADMIN_HEADERS,
                    json={"case_id": "sqlite-session-native-mcp-v1"},
                )
                evaluation = evaluation_response.json()
                replay_response = client.post(
                    f"/v1/run-submissions/{clean_2['preflight']['submission_id']}/confirm",
                    headers=SUBMIT_HEADERS,
                    json={"confirmation": clean_2["preflight"]["confirmation_challenge"]},
                )
                replay = replay_response.json()

                definition = AgentDefinitionCatalog(ROOT).resolve(AGENT_ID)
                binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
                runtime = app.state.session_runtime
                runtime.acquire_turn(
                    session_id=session_id,
                    run_id="run_step050_exclusive_a",
                    definition=definition,
                    runtime_binding_sha256=binding.runtime_binding_sha256,
                )
                clear_pending = client.post(
                    f"/v1/sessions/{session_id}/clear", headers=SUBMIT_HEADERS
                )
                competing_rejected = False
                try:
                    runtime.acquire_turn(
                        session_id=session_id,
                        run_id="run_step050_exclusive_b",
                        definition=definition,
                        runtime_binding_sha256=binding.runtime_binding_sha256,
                    )
                except SessionBusyError:
                    competing_rejected = True
                runtime.release_turn(
                    session_id=session_id,
                    run_id="run_step050_exclusive_a",
                    succeeded=False,
                    item_count=8,
                )
                final_session = client.get(
                    f"/v1/sessions/{session_id}", headers=ADMIN_HEADERS
                ).json()

            references_after = {
                item.reference_id: item.to_dict()
                for item in ReferenceCatalogService(ROOT).verify_all()
            }
            cases = {"clean_1": clean_1, "mcp_failure": failed, "clean_2": clean_2}
            all_events = [event for case in cases.values() for event in case["events"]]
            mcp_events = [event for event in all_events if event["source"] == "mcp"]
            session_started = [e for e in all_events if e["event_type"] == "session.turn.started"]
            session_completed = [e for e in all_events if e["event_type"] == "session.turn.completed"]
            history = _history_items(runtime, session_id)
            final_counts = _counts(product_db, evaluation_db)
            product_text = product_db.read_bytes().decode("utf-8", errors="ignore")
            evaluation_text = evaluation_db.read_bytes().decode("utf-8", errors="ignore")
            event_text = json.dumps(all_events, ensure_ascii=False)
            manager_order = captured["manager_order"]
            checks = {
                "session_api_auth_required": unauthenticated.status_code == 401,
                "session_created_for_exact_agent_and_binding": created.get("agent_definition_id") == AGENT_ID
                and created.get("runtime_binding_sha256") == binding.runtime_binding_sha256
                and binding.execution_path == "sqlite-session-native-mcp-execution-v1",
                "three_preflights_bound_same_session": all(
                    case["preflight"].get("session_id") == session_id for case in cases.values()
                ),
                "native_streaming_and_mcp_manager_used_three_times": counters["run"] == 0
                and counters["run_streamed"] == 3
                and counters["mcp_runtime_created"] == 3
                and counters["mcp_manager_enters"] == 3
                and counters["mcp_manager_exits"] == 3,
                "same_sdk_session_identity_used_three_times": captured["session_ids"] == [session_id] * 3,
                "exact_read_only_local_mcp_server_used": captured["manager_server_names"] == [["reference-catalog"]] * 3
                and captured["agent_mcp_server_names"] == [["reference-catalog"]] * 3
                and binding.mcp_servers[0]["server_id"] == "reference-catalog",
                "first_success_committed_complete_mcp_turn": clean_1["terminal"].get("status") == "SUCCEEDED"
                and after_clean_1.get("turn_count") == 1
                and after_clean_1.get("item_count") == 4,
                "mcp_failure_terminalized_same_run": failed["terminal"].get("status") == "FAILED"
                and any(
                    e["event_type"] == "run.failed" and e["payload"].get("code") == "SDK_RUN_FAILED"
                    for e in failed["events"]
                ),
                "mcp_failure_partial_history_rolled_back": after_failure.get("turn_count") == 1
                and after_failure.get("item_count") == 4
                and after_failure.get("active_run_id") is None,
                "mcp_manager_cleaned_before_history_rollback": manager_order.index("manager_exit_2")
                < manager_order.index("rollback_pop_2"),
                "later_success_received_only_committed_history": len(captured["history_before"]) == 3
                and len(captured["history_before"][2]) == 4
                and MARKER in json.dumps(captured["history_before"][2], ensure_ascii=False)
                and FAIL_SENTINEL not in json.dumps(captured["history_before"][2], ensure_ascii=False),
                "second_success_committed_complete_mcp_turn": clean_2["terminal"].get("status") == "SUCCEEDED"
                and after_clean_2.get("turn_count") == 2
                and after_clean_2.get("item_count") == 8,
                "one_mcp_tool_call_per_turn": counters["mcp_tool_calls"] == 3
                and len([e for e in mcp_events if e["event_type"] == "tool.started"]) == 3
                and len([e for e in mcp_events if e["event_type"] == "tool.completed"]) == 3,
                "mcp_event_metadata_safe": all(
                    event["payload"].get("server_id") == "reference-catalog"
                    and event["payload"].get("tool_name") == "search_reference"
                    and RAW_QUERY_SENTINEL not in json.dumps(event["payload"], ensure_ascii=False)
                    and RAW_RESULT_SENTINEL not in json.dumps(event["payload"], ensure_ascii=False)
                    for event in mcp_events
                ),
                "canonical_session_event_pairs_exact": len(session_started) == 3
                and len(session_completed) == 2
                and [e["payload"].get("item_count") for e in session_completed] == [4, 8],
                "all_root_invocations_terminal": all(
                    len(case["invocations"]) == 1
                    and case["invocations"][0]["invocation_kind"] == "ROOT"
                    and case["invocations"][0]["state"] in {"SUCCEEDED", "FAILED"}
                    for case in cases.values()
                ),
                "failed_run_created_no_artifact": not any(
                    e["event_type"] == "artifact.created" for e in failed["events"]
                ),
                "two_successful_artifacts_only": final_counts["artifacts"] == 2
                and artifact2.get("content", {}).get("status") == "PASS"
                and MARKER in artifact2.get("content", {}).get("summary", ""),
                "recorded_evaluation_passed": evaluation_response.status_code == 201
                and evaluation.get("state") == "PASSED"
                and evaluation.get("case_id") == "sqlite-session-native-mcp-v1",
                "confirmation_replay_no_duplicate": replay_response.status_code in {200, 202}
                and replay.get("replayed") is True
                and replay.get("scheduled") is False,
                "clear_rejected_while_turn_lease_held": clear_pending.status_code == 409,
                "competing_turn_rejected_while_lease_held": competing_rejected,
                "failed_exclusivity_probe_did_not_commit_turn": final_session.get("turn_count") == 2
                and final_session.get("item_count") == 8
                and final_session.get("active_run_id") is None,
                "sdk_history_contains_only_two_successful_mcp_turns": len(history) == 8
                and MARKER in json.dumps(history, ensure_ascii=False)
                and FAIL_SENTINEL not in json.dumps(history, ensure_ascii=False),
                "raw_session_and_mcp_content_not_in_product_events": MARKER not in event_text
                and FAIL_SENTINEL not in event_text
                and RAW_QUERY_SENTINEL not in event_text
                and RAW_RESULT_SENTINEL not in event_text,
                "raw_requests_and_api_key_not_in_product_or_evaluation_db": all(
                    value not in product_text and value not in evaluation_text
                    for value in REQUESTS.values()
                )
                and HIDDEN_API_KEY not in product_text
                and HIDDEN_API_KEY not in evaluation_text,
                "payload_retention_exact": clean_1["submission"].get("payload_retention_state") == "DELETED"
                and clean_2["submission"].get("payload_retention_state") == "DELETED"
                and failed["submission"].get("payload_retention_state") == "RETAINED"
                and len(list(payload_root.glob("payload_*.json"))) == 1,
                "session_handles_closed": counters["session_instances"] == 6
                and counters["session_closes"] == 6,
                "final_product_counts_exact": final_counts == {
                    "tasks": 3,
                    "runs": 3,
                    "submissions": 3,
                    "invocations": 3,
                    "events": len(all_events),
                    "artifacts": 2,
                    "evaluations": 1,
                },
                "references_unchanged": references_before == references_after,
                "cleanup_completed": True,
            }
            report = {
                "schema_version": "okcanvas-step050-acceptance-v1",
                "state": "PASSED" if all(checks.values()) else "FAILED",
                "checks": checks,
                "session": {
                    "session_id": session_id,
                    "runtime_binding_sha256": binding.runtime_binding_sha256,
                    "after_clean_1": after_clean_1,
                    "after_mcp_failure": after_failure,
                    "after_clean_2": after_clean_2,
                    "final": final_session,
                    "history_item_count": len(history),
                },
                "cases": {
                    name: {
                        "run_id": case["confirmed"]["run_id"],
                        "status": case["terminal"].get("status"),
                        "event_count": len(case["events"]),
                        "mcp_tool_count": len(
                            [e for e in case["events"] if e["source"] == "mcp" and e["event_type"] == "tool.started"]
                        ),
                    }
                    for name, case in cases.items()
                },
                "gateway_counts": counters,
                "manager_order": manager_order,
                "final_counts": final_counts,
                "protected_payload_file_count": len(list(payload_root.glob("payload_*.json"))),
                "evaluation": evaluation,
                "replay": replay,
            }
            final = workspace.finalize(report)
            final["checks"]["cleanup_completed"] = (
                final["acceptance_workspace"]["cleanup_state"] == "COMPLETED"
            )
            final["state"] = "PASSED" if all(final["checks"].values()) else "FAILED"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(final, ensure_ascii=False, indent=2))
            return 0 if final["state"] == "PASSED" else 1
    finally:
        _restore(previous_version, previous_modules, previous_factory)
        if previous_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = previous_key


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/evidence/STEP050_ACCEPTANCE.json",
    )
    args = parser.parse_args()
    return run_acceptance(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
